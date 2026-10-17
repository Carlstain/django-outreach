from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus, ProspectStatus
from outreach.models import Mailing, MailingDelivery
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailQueueTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")

    def queue(self, prospects: list) -> object:
        return self.mailer.queue(prospects, "Subject", "<p>Body</p>", "", True)

    def test_each_recipient_gets_a_pending_delivery_and_is_claimed(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        queued_mailing = self.queue(prospects)

        self.assertEqual(
            set(MailingDelivery.objects.values_list("prospect", flat=True)),
            {prospect.pk for prospect in prospects},
        )
        self.assertEqual(
            set(MailingDelivery.objects.values_list("status", flat=True)),
            {DeliveryStatus.PENDING},
        )
        self.assertEqual(len(queued_mailing.deliveries), 2)
        for prospect in prospects:
            prospect.refresh_from_db()
            self.assertIsNotNone(prospect.last_mailed_at)
            self.assertEqual(prospect.status, ProspectStatus.PROSPECT)

    def test_the_delivery_keeps_the_mailed_date_that_the_claim_replaced(self) -> None:
        previous_mailed_at = timezone.now() - timedelta(days=3)
        prospect = ProspectFactory(last_mailed_at=previous_mailed_at)

        self.queue([prospect])

        self.assertEqual(MailingDelivery.objects.get().previous_mailed_at, previous_mailed_at)

    def test_skipped_prospects_get_no_delivery_and_are_counted(self) -> None:
        mailable = ProspectFactory()
        unsubscribed = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)

        queued_mailing = self.queue([mailable, unsubscribed])

        mailing = queued_mailing.mailing
        self.assertEqual(MailingDelivery.objects.get().prospect, mailable)
        self.assertEqual(mailing.skipped_count, 1)
        self.assertEqual(mailing.skipped_reasons["unsubscribed"], 1)

    def test_nobody_to_mail_creates_no_mailing(self) -> None:
        unsubscribed = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)

        queued_mailing = self.queue([unsubscribed])

        self.assertIsNone(queued_mailing.mailing)
        self.assertEqual(Mailing.objects.count(), 0)
        self.assertEqual(MailingDelivery.objects.count(), 0)

    @override_settings(
        OUTREACH_DISPATCH="sync",
        OUTREACH_MAX_RECIPIENTS_PER_SEND=2,
        OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND=3,
    )
    def test_sync_mode_applies_the_sync_cap(self) -> None:
        queued_mailing = self.queue([ProspectFactory() for _ in range(3)])

        self.assertEqual(MailingDelivery.objects.count(), 2)
        self.assertEqual(queued_mailing.mailing.skipped_reasons["over_limit"], 1)

    @override_settings(
        OUTREACH_DISPATCH="celery",
        OUTREACH_MAX_RECIPIENTS_PER_SEND=1,
        OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND=3,
    )
    def test_celery_mode_applies_the_celery_cap(self) -> None:
        queued_mailing = self.queue([ProspectFactory() for _ in range(4)])

        self.assertEqual(MailingDelivery.objects.count(), 3)
        self.assertEqual(queued_mailing.mailing.skipped_reasons["over_limit"], 1)
