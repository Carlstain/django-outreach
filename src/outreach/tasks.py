from math import ceil

from celery import shared_task
from django.utils import timezone

from outreach.conf import outreach_settings
from outreach.models import MailingDelivery
from outreach.services.mailing import ProspectMailer, TransientDeliveryError
from outreach.services.scheduling import MailingScheduler
from outreach.services.send_gate import SendGate

RETRY_BASE_DELAY_SECONDS = 60
MAX_WAKE_UP_SECONDS = 300


@shared_task(bind=True, name="outreach.deliver_mail")
def deliver_mail(self, delivery_pk: str) -> str | None:
    sender = (
        MailingDelivery.objects.filter(pk=delivery_pk)
        .values_list("mailing__sender", flat=True)
        .first()
    )
    if sender is None:
        return None
    mailer = ProspectMailer.from_settings(sender)
    try:
        status = mailer.deliver(delivery_pk, may_retry=True)
    except TransientDeliveryError as error:
        countdown = RETRY_BASE_DELAY_SECONDS * 2**self.request.retries
        raise self.retry(exc=error, countdown=countdown, max_retries=None) from error
    return status.value if status else None


@shared_task(name="outreach.send_due_mailings")
def send_due_mailings() -> int:
    return MailingScheduler.start_due()


@shared_task(name="outreach.release_deliveries")
def release_deliveries() -> int:
    outcome = SendGate.release_due()
    if outcome.next_run_at is not None:
        seconds_until_next_run = (outcome.next_run_at - timezone.now()).total_seconds()
        countdown = min(max(ceil(seconds_until_next_run), 1), MAX_WAKE_UP_SECONDS)
        release_deliveries.apply_async(
            countdown=countdown, queue=outreach_settings.celery_queue
        )
    return outcome.released
