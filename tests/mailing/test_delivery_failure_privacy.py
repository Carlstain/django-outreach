from smtplib import SMTPDataError, SMTPRecipientsRefused, SMTPServerDisconnected
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.choices import DeliveryStatus, EventKind, FailureKind
from outreach.models import ProspectEvent
from outreach.services.mailing import ProspectMailer, TransientDeliveryError
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory

SERVER_REPLY = b"5.1.1 mailbox unavailable for this user"


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class DeliveryFailurePrivacyTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.prospect = ProspectFactory(email="private.person@example.org")
        queued_mailing = self.mailer.queue([self.prospect], "Subject", "<p>Body</p>", "", True)
        self.delivery = queued_mailing.deliveries[0]
        self.refusal = SMTPRecipientsRefused({self.prospect.email: (550, SERVER_REPLY)})

    def fail_with(self, error: Exception, **deliver_options: bool) -> None:
        with patch.object(EmailMultiAlternatives, "send", side_effect=error):
            self.mailer.deliver(self.delivery.pk, **deliver_options)

    def test_a_failure_keeps_a_kind_and_nothing_the_server_said(self) -> None:
        self.fail_with(self.refusal)

        self.delivery.refresh_from_db()
        event = ProspectEvent.objects.get(prospect=self.prospect, kind=EventKind.MAIL_FAILED)
        self.assertEqual(self.delivery.status, DeliveryStatus.FAILED)
        self.assertEqual(self.delivery.failure_kind, FailureKind.REFUSED)
        self.assertEqual(event.detail, FailureKind.REFUSED)
        for stored in (self.delivery.failure_kind, event.detail):
            self.assertNotIn("private.person", stored)
            self.assertNotIn("mailbox", stored)

    def test_the_log_names_the_kind_and_the_exception_class_but_no_address(self) -> None:
        with self.assertLogs("outreach", level="WARNING") as logs:
            self.fail_with(self.refusal)

        self.assertEqual(len(logs.records), 1)
        message = logs.records[0].getMessage()
        self.assertIn(str(self.delivery.pk), message)
        self.assertIn("refused", message)
        self.assertIn("SMTPRecipientsRefused", message)
        self.assertNotIn("private.person", message)
        self.assertNotIn("mailbox", message)
        self.assertIsNone(logs.records[0].exc_info)

    def test_the_log_carries_the_smtp_code_and_still_none_of_the_reply_text(self) -> None:
        with self.assertLogs("outreach", level="WARNING") as logs:
            self.fail_with(SMTPDataError(554, b"rejected for private.person@example.org"))

        message = logs.records[0].getMessage()
        self.assertTrue(message.endswith("(SMTPDataError) smtp 554"))
        self.assertNotIn("private.person", message)
        self.assertNotIn("rejected", message)

    def test_the_log_carries_the_code_of_a_recipient_refusal(self) -> None:
        with self.assertLogs("outreach", level="WARNING") as logs:
            self.fail_with(self.refusal)

        self.assertTrue(
            logs.records[0].getMessage().endswith("(SMTPRecipientsRefused) smtp 550")
        )

    def test_a_non_smtp_failure_logs_no_code(self) -> None:
        with self.assertLogs("outreach", level="WARNING") as logs:
            self.fail_with(ValueError("bad button"))

        self.assertTrue(logs.records[0].getMessage().endswith("(ValueError)"))

    def test_a_retry_after_a_transient_error_carries_the_kind_only(self) -> None:
        with self.assertRaises(TransientDeliveryError) as raised:
            self.fail_with(
                SMTPServerDisconnected("down for private.person@example.org"), may_retry=True
            )

        self.assertEqual(str(raised.exception), "server")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryStatus.PENDING)
        self.assertEqual(self.delivery.failure_kind, FailureKind.SERVER)

    def test_the_label_of_the_event_is_the_kind_and_an_old_raw_detail_shows_nothing(
        self,
    ) -> None:
        self.fail_with(self.refusal)
        event = ProspectEvent.objects.get(prospect=self.prospect, kind=EventKind.MAIL_FAILED)
        old_event = ProspectEvent.record(
            self.prospect,
            EventKind.MAIL_FAILED,
            "staff",
            "raw error for private.person@example.org",
        )
        other_event = ProspectEvent.record(
            self.prospect, EventKind.MAILED, "staff", "A subject"
        )

        self.assertEqual(event.detail_label, "The mail server refused it")
        self.assertEqual(old_event.detail_label, "")
        self.assertEqual(other_event.detail_label, "A subject")
