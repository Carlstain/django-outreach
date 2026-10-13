from celery import shared_task
from django.core.exceptions import ImproperlyConfigured

from outreach.conf import outreach_settings
from outreach.models import MailingDelivery
from outreach.services.mailing import ProspectMailer, TransientDeliveryError

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
    base_url = outreach_settings.base_url
    if base_url is None:
        raise ImproperlyConfigured("OUTREACH_BASE_URL is not set, mail cannot be delivered.")
    mailer = ProspectMailer(base_url=base_url, actor=sender)
    try:
        status = mailer.deliver(delivery_pk, may_retry=True)
    except TransientDeliveryError as error:
        countdown = RETRY_BASE_DELAY_SECONDS * 2**self.request.retries
        raise self.retry(exc=error, countdown=countdown, max_retries=None) from error
    return status.value if status else None
