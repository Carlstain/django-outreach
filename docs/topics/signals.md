# Signals and subscribing

Outreach sends Django signals, so a host project can follow what happens without reading the
tables, and offers one call to create a prospect from the host's own signup form.

## Signals

They are defined in `outreach.signals`. Every one is sent after the transaction commits, so a
receiver always sees committed data, and with `send_robust`: a receiver that raises is logged by
Django on the `django.dispatch` logger and never breaks a send or an unsubscribe.

| Signal | Sent when | Arguments |
|---|---|---|
| `prospect_subscribed` | `ProspectSubscriptions.subscribe` created a prospect that is not unsubscribed | `prospect`, `consent_source` |
| `prospect_unsubscribed` | A prospect becomes unsubscribed, by link, by staff or by the API. Not sent again for one that already is | `prospect`, `actor` |
| `prospect_erased` | Staff erased a prospect with *Erase and suppress*. The prospect no longer exists | `email`, `actor` |
| `mail_sent` | A delivery was handed to the mail server | `delivery`, `mailing`, `prospect` |
| `mail_failed` | A delivery failed for good, after any retries | `delivery`, `mailing`, `prospect` |

The sender is the service class that sends the signal (`ProspectUnsubscriber`,
`ProspectSubscriptions`, `ProspectMailer`).

```python
from django.dispatch import receiver

from outreach.signals import prospect_unsubscribed


@receiver(prospect_unsubscribed)
def forget_in_crm(sender, prospect, actor, **kwargs):
    crm.unsubscribe(prospect.email)
```

Connect receivers in your own `AppConfig.ready`. Only `prospect_erased` carries an address, because the host needs it to erase its own copy.
A signal never carries the error text of a failed
delivery, and none is stored: `mail_failed` gives you the `delivery`, whose `failure_kind` says why.

There is deliberately no signal on `Prospect.save`: an account or an import is not consent, and
the events above are the ones that mean something.

## Subscribing from your own form

Outreach has no public subscribe form and no double opt-in. If your project collects consent
itself, call {class}`~outreach.services.subscription.ProspectSubscriptions` once it has it:

```python
from outreach.services.subscription import ProspectSubscriptions

result = ProspectSubscriptions().subscribe(
    "ada@example.org",
    consent_source="newsletter form, footer",
    first_name="Ada",
)
if result.created:
    ...
```

- `consent_source` is required and is kept in the *subscribed* event of the prospect, so you can
  show later where the consent came from.
- An existing prospect is returned unchanged (`created` is false). An unsubscribed one stays
  unsubscribed: nothing re-activates an address.
- A new prospect goes through `Prospect.save`, so the address is lower-cased, a suppressed address
  is created as unsubscribed and a matching user is linked.
- A bad address raises `django.core.exceptions.ValidationError`, an empty `consent_source`
  `ValueError`.

The host owns the consent: checking the box, a confirmation mail, any double opt-in.
