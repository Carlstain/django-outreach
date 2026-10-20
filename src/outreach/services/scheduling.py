from collections.abc import Iterable
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from outreach.choices import DeliveryStatus, SkipReason
from outreach.conf import outreach_settings
from outreach.models import Mailing, MailingDelivery, Prospect
from outreach.services.mailing import MailReport, ProspectMailer


class SchedulingUnavailable(Exception):
    """Scheduling needs ``OUTREACH_DISPATCH = "celery"``."""


class MailingScheduler:
    """Holds a mailing until it is due, then claims its recipients and queues the mail.

    A scheduled mailing keeps its recipients as ``scheduled`` deliveries and claims nobody, so
    the cooldown of other sends is not disturbed while it waits. ``start_due`` is called by the
    ``outreach.send_due_mailings`` task, run by Celery beat, or by the
    ``outreach_send_due_mailings`` command.
    """

    def __init__(self, mailer: ProspectMailer) -> None:
        self.mailer = mailer

    def schedule(
        self,
        prospects: Iterable[Prospect],
        subject: str,
        body_html: str,
        *,
        send_at: datetime,
        header_text: str = "",
        is_newsletter: bool = True,
        language: str = "",
    ) -> MailReport:
        """Store a mailing to start at ``send_at``. ``MailReport.scheduled`` lists the recipients.

        The recipients are chosen now, with the same rules as a send. The cooldown is checked
        again when the mailing starts.

        Raises:
            SchedulingUnavailable: ``OUTREACH_DISPATCH`` is not ``"celery"``.
        """
        self.require_celery()
        queued_mailing = self.mailer.queue(
            prospects,
            subject,
            body_html,
            header_text,
            is_newsletter,
            language,
            send_at=send_at,
        )
        return MailReport(
            mailing=queued_mailing.mailing,
            scheduled=[delivery.prospect for delivery in queued_mailing.deliveries],
            skipped=list(queued_mailing.plan.skipped),
        )

    @classmethod
    def start(cls, mailing: Mailing) -> int:
        """Claim the recipients of a scheduled mailing and queue one task for each.

        A recipient mailed by another mailing within ``OUTREACH_RESEND_COOLDOWN`` since the
        schedule is skipped and counted. Nothing happens for a mailing already started.

        Returns:
            The number of deliveries queued.

        Raises:
            SchedulingUnavailable: ``OUTREACH_DISPATCH`` is not ``"celery"``.
        """
        cls.require_celery()
        with transaction.atomic():
            scheduled_deliveries = list(
                MailingDelivery.objects.select_for_update(
                    skip_locked=True, of=("self", "prospect")
                )
                .select_related("prospect")
                .filter(mailing=mailing, status=DeliveryStatus.SCHEDULED)
            )
            claimed_at = timezone.now()
            ready_deliveries = []
            held_deliveries = []
            for delivery in scheduled_deliveries:
                if ProspectMailer.is_in_cooldown(delivery.prospect.last_mailed_at, claimed_at):
                    held_deliveries.append(delivery)
                else:
                    ready_deliveries.append(delivery)
            ProspectMailer.claim(ready_deliveries, claimed_at)
            if held_deliveries:
                MailingDelivery.objects.filter(
                    pk__in=[delivery.pk for delivery in held_deliveries]
                ).update(status=DeliveryStatus.SKIPPED, updated_at=claimed_at)
                ProspectMailer.skip_in_mailing(
                    mailing, SkipReason.COOLDOWN, len(held_deliveries)
                )
        ProspectMailer.submit(delivery.pk for delivery in ready_deliveries)
        return len(ready_deliveries)

    @classmethod
    def start_due(cls) -> int:
        """Start every mailing whose time has come. Returns how many mailings were handled."""
        scheduled_mailing_pks = MailingDelivery.objects.filter(
            status=DeliveryStatus.SCHEDULED
        ).values("mailing_id")
        due_mailings = Mailing.objects.filter(
            scheduled_for__lte=timezone.now(), pk__in=scheduled_mailing_pks
        ).only("pk")
        handled_count = 0
        for mailing in due_mailings:
            cls.start(mailing)
            handled_count += 1
        return handled_count

    @staticmethod
    def cancel(mailing: Mailing) -> bool:
        """Delete a mailing that has not started. Returns whether it was deleted."""
        with transaction.atomic():
            statuses = set(
                MailingDelivery.objects.select_for_update()
                .filter(mailing=mailing)
                .values_list("status", flat=True)
            )
            if statuses != {DeliveryStatus.SCHEDULED}:
                return False
            mailing.delete()
        return True

    @staticmethod
    def require_celery() -> None:
        if not outreach_settings.uses_celery:
            raise SchedulingUnavailable('Scheduling needs OUTREACH_DISPATCH = "celery".')
