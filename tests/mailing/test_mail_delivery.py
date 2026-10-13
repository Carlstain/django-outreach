from smtplib import SMTPRecipientsRefused, SMTPServerDisconnected
from unittest.mock import patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.choices import DeliveryStatus, EventKind, ProspectStatus, SkipReason
from outreach.models import MailingDelivery, ProspectEvent
from outreach.services.mailing import ProspectMailer, TransientDeliveryError
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailDeliveryTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.prospect = ProspectFactory()
        queued_mailing = self.mailer.queue([self.prospect], "Subject", "<p>Body</p>", "", True)
        self.mailing = queued_mailing.mailing
        self.delivery = queued_mailing.deliveries[0]

    def test_a_delivery_is_sent_and_recorded(self) -> None:
        status = self.mailer.deliver(self.delivery.pk)

        self.assertEqual(status, DeliveryStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.delivery.refresh_from_db()
        self.mailing.refresh_from_db()
        self.prospect.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryStatus.SENT)
        self.assertEqual(self.mailing.sent_count, 1)
        self.assertEqual(self.prospect.status, ProspectStatus.CONTACTED)
        self.assertTrue(
            ProspectEvent.objects.filter(
                prospect=self.prospect, kind=EventKind.MAILED
            ).exists()
        )

    def test_a_delivery_that_is_not_pending_is_left_alone(self) -> None:
        self.mailer.deliver(self.delivery.pk)

        status = self.mailer.deliver(self.delivery.pk)

        self.assertIsNone(status)
        self.assertEqual(len(mail.outbox), 1)

    def test_a_prospect_who_unsubscribed_after_queuing_is_skipped(self) -> None:
        self.prospect.status = ProspectStatus.UNSUBSCRIBED
        self.prospect.save()

        status = self.mailer.deliver(self.delivery.pk)

        self.assertEqual(status, DeliveryStatus.SKIPPED)
        self.assertEqual(len(mail.outbox), 0)
        self.prospect.refresh_from_db()
        self.mailing.refresh_from_db()
        self.assertIsNone(self.prospect.last_mailed_at)
        self.assertEqual(self.mailing.skipped_count, 1)
        self.assertEqual(self.mailing.skipped_reasons["unsubscribed"], 1)
        self.assertEqual(
            set(self.mailing.skipped_reasons), {reason.value for reason in SkipReason}
        )

    def test_a_permanent_error_fails_the_delivery_and_restores_the_claim(self) -> None:
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
        ):
            status = self.mailer.deliver(self.delivery.pk, may_retry=True)

        self.assertEqual(status, DeliveryStatus.FAILED)
        self.delivery.refresh_from_db()
        self.mailing.refresh_from_db()
        self.prospect.refresh_from_db()
        self.assertEqual((self.delivery.status, self.delivery.attempts), ("failed", 1))
        self.assertEqual(self.mailing.failed_count, 1)
        self.assertIsNone(self.prospect.last_mailed_at)
        self.assertTrue(
            ProspectEvent.objects.filter(
                prospect=self.prospect, kind=EventKind.MAIL_FAILED
            ).exists()
        )

    def test_a_transient_error_is_raised_and_keeps_the_claim(self) -> None:
        with (
            patch.object(
                EmailMultiAlternatives, "send", side_effect=SMTPServerDisconnected("down")
            ),
            self.assertRaises(TransientDeliveryError),
        ):
            self.mailer.deliver(self.delivery.pk, may_retry=True)

        self.delivery.refresh_from_db()
        self.prospect.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryStatus.PENDING)
        self.assertEqual(self.delivery.attempts, 1)
        self.assertEqual(self.delivery.last_error, "down")
        self.assertIsNotNone(self.prospect.last_mailed_at)

    @override_settings(OUTREACH_DELIVERY_MAX_RETRIES=1)
    def test_a_transient_error_fails_once_the_retries_are_used(self) -> None:
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPServerDisconnected("down")
        ):
            with self.assertRaises(TransientDeliveryError):
                self.mailer.deliver(self.delivery.pk, may_retry=True)
            status = self.mailer.deliver(self.delivery.pk, may_retry=True)

        self.assertEqual(status, DeliveryStatus.FAILED)
        self.assertEqual(MailingDelivery.objects.get().attempts, 2)
        self.prospect.refresh_from_db()
        self.assertIsNone(self.prospect.last_mailed_at)

    def test_a_transient_error_fails_at_once_without_retries(self) -> None:
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPServerDisconnected("down")
        ):
            status = self.mailer.deliver(self.delivery.pk)

        self.assertEqual(status, DeliveryStatus.FAILED)
