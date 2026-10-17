from smtplib import SMTPRecipientsRefused
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.choices import DeliveryStatus
from outreach.models import Mailing, MailingDelivery
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class InterruptedSendTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.prospects = [ProspectFactory() for _ in range(3)]

    def test_an_interrupted_send_deletes_the_unreached_deliveries_and_releases_them(
        self,
    ) -> None:
        with (
            patch.object(
                ProspectMailer,
                "deliver",
                side_effect=[DeliveryStatus.SENT, RuntimeError("worker killed")],
            ),
            self.assertRaises(RuntimeError),
        ):
            self.mailer.send(self.prospects, "Subject", "<p>Body</p>")

        self.assertEqual(MailingDelivery.objects.count(), 1)
        reached, *unreached = [prospect for prospect in self.prospects]
        self.assertEqual(MailingDelivery.objects.get().prospect, reached)
        for prospect in unreached:
            prospect.refresh_from_db()
            self.assertIsNone(prospect.last_mailed_at)

    def test_an_interrupted_retry_puts_the_unreached_deliveries_back_to_failed(self) -> None:
        queued_mailing = self.mailer.queue(self.prospects, "Subject", "<p>Body</p>", "", True)
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
        ):
            for delivery in queued_mailing.deliveries:
                self.mailer.deliver(delivery.pk)
        mailing = Mailing.objects.get(pk=queued_mailing.mailing.pk)
        self.assertEqual(mailing.failed_count, 3)

        with (
            patch.object(
                ProspectMailer,
                "deliver",
                side_effect=[DeliveryStatus.SENT, RuntimeError("worker killed")],
            ),
            self.assertRaises(RuntimeError),
        ):
            self.mailer.retry(mailing)

        statuses = [
            MailingDelivery.objects.get(mailing=mailing, prospect=prospect).status
            for prospect in self.prospects
        ]
        self.assertEqual(
            sorted(statuses),
            sorted([DeliveryStatus.PENDING, DeliveryStatus.FAILED, DeliveryStatus.FAILED]),
        )
        mailing.refresh_from_db()
        self.assertEqual(mailing.failed_count, 2)
        for prospect in self.prospects:
            prospect.refresh_from_db()
        self.assertEqual(
            sum(prospect.last_mailed_at is None for prospect in self.prospects), 2
        )
