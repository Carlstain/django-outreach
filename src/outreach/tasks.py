from celery import shared_task

from outreach.models import MailingDelivery
from outreach.services.mailing import ProspectMailer, TransientDeliveryError
from outreach.services.scheduling import MailingScheduler

RETRY_BASE_DELAY_SECONDS = 60


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
