from unittest.mock import patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.models import Mailing, MailingDelivery, Prospect, ProspectEvent
from outreach.services.failures import MessageNotAccepted
from outreach.services.mailing import ProspectMailer
from outreach.services.unsubscribe import UnsubscribeTokens
from outreach.signals import mail_failed, mail_sent
from tests.base import MAIL_BASE_URL, OutreachMailTagTestCase
from tests.factories import ProspectFactory

STAFF_EMAIL = "staff.member@example.org"


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class SendSampleTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.prospect = ProspectFactory(first_name="Ada", email="ada@example.org")

    def send_sample(self, subject: str = "Hello {{ first_name }}", **options: object) -> None:
        self.mailer.send_sample(
            self.prospect, subject, "<p>Dear {{ first_name }}</p>", STAFF_EMAIL, **options
        )

    def test_one_test_mail_goes_to_the_given_address_only_with_the_prospects_details(
        self,
    ) -> None:
        self.send_sample()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [STAFF_EMAIL])
        self.assertEqual(message.subject, "[Test] Hello Ada")
        self.assertIn("Dear Ada", message.alternatives[0][0])
        self.assertNotIn(self.prospect.email, message.to)

    def test_the_copy_can_not_unsubscribe_the_prospect(self) -> None:
        self.send_sample()

        message = mail.outbox[0]
        token = UnsubscribeTokens().make(self.prospect)
        self.assertNotIn("List-Unsubscribe", message.extra_headers)
        self.assertNotIn("List-Unsubscribe-Post", message.extra_headers)
        self.assertNotIn(token, message.body)
        self.assertNotIn(token, message.alternatives[0][0])
        self.assertIn(f'href="{MAIL_BASE_URL}/"', message.alternatives[0][0])

    def test_nothing_is_written_and_no_signal_is_sent(self) -> None:
        sent_receiver = self.connect_receiver(mail_sent)
        failed_receiver = self.connect_receiver(mail_failed)

        with self.captureOnCommitCallbacks(execute=True):
            self.send_sample()

        self.assertEqual(Mailing.objects.count(), 0)
        self.assertEqual(MailingDelivery.objects.count(), 0)
        self.assertEqual(ProspectEvent.objects.count(), 0)
        prospect = Prospect.objects.get(pk=self.prospect.pk)
        self.assertIsNone(prospect.last_mailed_at)
        self.assertEqual(prospect.status, self.prospect.status)
        sent_receiver.assert_not_called()
        failed_receiver.assert_not_called()

    def test_tags_that_declare_preview_get_true(self) -> None:
        values: list[bool] = []

        def probe(prospect: Prospect, *, preview: bool = False) -> str:
            values.append(preview)
            return "previewing" if preview else "sending"

        self.register_tag(probe, "probe")

        self.send_sample(subject="{% probe %}")

        self.assertEqual(values, [True])
        self.assertEqual(mail.outbox[0].subject, "[Test] previewing")

    def test_a_server_that_delivers_nothing_raises(self) -> None:
        with (
            patch.object(EmailMultiAlternatives, "send", return_value=0),
            self.assertRaises(MessageNotAccepted),
        ):
            self.send_sample()
