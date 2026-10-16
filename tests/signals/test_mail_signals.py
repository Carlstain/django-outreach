from smtplib import SMTPRecipientsRefused
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.choices import ProspectStatus
from outreach.services.mailing import ProspectMailer
from outreach.signals import mail_failed, mail_sent
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailSignalTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.prospect = ProspectFactory()
        queued_mailing = self.mailer.queue([self.prospect], "Subject", "<p>Body</p>", "", True)
        self.mailing = queued_mailing.mailing
        self.delivery = queued_mailing.deliveries[0]
        self.sent_receiver = self.connect_receiver(mail_sent)
        self.failed_receiver = self.connect_receiver(mail_failed)

    def test_a_sent_delivery_sends_mail_sent_after_commit(self) -> None:
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.mailer.deliver(self.delivery.pk)

        self.sent_receiver.assert_not_called()
        for callback in callbacks:
            callback()
        self.sent_receiver.assert_called_once()
        arguments = self.sent_receiver.call_args.kwargs
        self.assertEqual(arguments["sender"], ProspectMailer)
        self.assertEqual(arguments["mailing"], self.mailing)
        self.assertEqual(arguments["prospect"], self.prospect)
        self.assertEqual(arguments["delivery"].pk, self.delivery.pk)
        self.failed_receiver.assert_not_called()

    def test_a_failed_delivery_sends_mail_failed(self) -> None:
        with (
            patch.object(
                EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.mailer.deliver(self.delivery.pk)

        self.failed_receiver.assert_called_once()
        arguments = self.failed_receiver.call_args.kwargs
        self.assertEqual(arguments["mailing"], self.mailing)
        self.assertEqual(arguments["prospect"], self.prospect)
        self.assertEqual(arguments["delivery"].pk, self.delivery.pk)
        self.sent_receiver.assert_not_called()

    def test_a_skipped_delivery_sends_neither_signal(self) -> None:
        self.prospect.status = ProspectStatus.UNSUBSCRIBED
        self.prospect.save()

        with self.captureOnCommitCallbacks(execute=True):
            self.mailer.deliver(self.delivery.pk)

        self.sent_receiver.assert_not_called()
        self.failed_receiver.assert_not_called()
