# Sending with Celery

By default a send runs inside the admin request, one SMTP message after the other. That is
simple and needs no broker, but it holds the request open (about 0.3 s per message), has no
retry and is capped at `OUTREACH_MAX_RECIPIENTS_PER_SEND` (100) to fit under a proxy timeout.

:::{warning}
Synchronous sending is **not recommended in production**. `manage.py check --deploy` reports
it as `outreach.W001`. Use Celery for any real mailing list.
:::

## How it works

With `OUTREACH_DISPATCH = "celery"` a send action does only the quick part inside the request:
it claims the recipients, creates the `Mailing` and one `MailingDelivery` per recipient (status
`pending`), and queues one `outreach.deliver_mail` task per delivery after the transaction
commits. The admin answers "N queued, M skipped". Each task sends one mail and records the
outcome on the delivery and the mailing counts.

- A transient error (the server is unreachable, disconnects or times out) is retried with an
  exponential backoff (60 s, 120 s, 240 s, ...), up to `OUTREACH_DELIVERY_MAX_RETRIES` retries.
- A permanent error (recipient refused, empty button link, a tag that raises, a server that
  accepts nothing) fails the recipient at once. The claim is restored and a `mail_failed` event
  is recorded, as in synchronous mode.
- Recipients are capped by `OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND` (default 5000) instead of
  `OUTREACH_MAX_RECIPIENTS_PER_SEND`.

## Set it up

Outreach does not create a Celery app. It registers its task with `shared_task`, so it uses the
app of the host project, with the host's broker and settings. If the project has no Celery app
yet, create one as described in the
[Celery guide for Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html):

```python
# mysite/celery.py
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

app = Celery("mysite")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

```python
# mysite/__init__.py
from .celery import app as celery_app

__all__ = ["celery_app"]
```

The web process must import the app (the `__init__.py` above does it), otherwise Celery falls
back to a default app without your broker and queuing fails. There is no startup check for it,
because Celery keeps the current app per thread and a check cannot tell reliably.

Then install the extra and turn the mode on:

```shell
pip install "django-outreach[celery]"
```

```python
OUTREACH_DISPATCH = "celery"
CELERY_BROKER_URL = "redis://localhost:6379/0"
```

Start a worker as usual (`celery -A mysite worker`).

## Scheduling a send

In Celery mode the compose page of a mail has a *Send at* field. Leave it empty to send now, or
choose a time to have the mail go out then. The time is read in the time zone of the project.

A scheduled mailing keeps its recipients as `scheduled` deliveries and claims nobody. When its
time comes, the recipients are claimed, one task is queued for each, and from then on it works
like any other send. So nobody is held back from other mailings while it waits, and a recipient
mailed by another mailing within `OUTREACH_RESEND_COOLDOWN` in the meantime is skipped and
counted. People who unsubscribed in the meantime are skipped when their mail is delivered, as
always. The recipients are chosen when you schedule, with the same rules as a send.

**Something has to start it.** Outreach has no clock of its own, so a scheduled mailing is only
sent when you run one of these, every minute or so:

```python
# settings.py, with Celery beat
CELERY_BEAT_SCHEDULE = {
    "outreach-send-due-mailings": {
        "task": "outreach.send_due_mailings",
        "schedule": 60.0,
    },
}
```

```shell
# or from cron, without beat
* * * * * cd /srv/mysite && python manage.py outreach_send_due_mailings
```

Without one of them a scheduled mailing stays scheduled for ever. The mailing page says *Scheduled
for* until it starts, and a *Cancel the schedule* button deletes it while it has not started.

Scheduling is not available in synchronous mode, and the field is not shown. If you switch back to
synchronous mode, mailings still scheduled stay scheduled and the command refuses to start them:
cancel them or switch back. A mailing is only sent at the first run after its time, so a one
minute schedule means up to a minute late.

## Queue and rate limit

To use a separate queue, set `OUTREACH_CELERY_QUEUE = "outreach"` and start a worker for it
with `celery -A mysite worker -Q outreach`.

Outreach has no rate limit setting. Celery fixes a task's rate limit when the task is defined,
so set it in your own Celery configuration, for example to stay under the limit of your mail
provider:

```python
CELERY_TASK_ANNOTATIONS = {"outreach.deliver_mail": {"rate_limit": "10/s"}}
```

## When a worker dies

Celery delivers a task at least once. If a worker is killed, or the broker loses messages, a
delivery stays `pending` and its prospect stays claimed (so the cooldown still applies). Queue
those deliveries again with:

```shell
python manage.py outreach_resume_deliveries --older-than 30
```

A delivery is only sent while it is `pending`, so a task that runs twice sends once. One
window remains: if a worker dies after the mail server accepted a message but before the
database records it, a resumed delivery sends that one message a second time.

If the broker is unreachable when a send action runs, the action fails after the deliveries
were created. The same command recovers them once the broker is back.
