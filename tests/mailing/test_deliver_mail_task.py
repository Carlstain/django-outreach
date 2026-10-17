import uuid
from smtplib import SMTPServerDisconnected
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.choices import DeliveryStatus
from outreach.models import MailingDelivery
from outreach.services.mailing import ProspectMailer
from outreach.tasks import deliver_mail
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class DeliverMailTaskTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospect = ProspectFactory()
        queued_mailing = ProspectMailer(MAIL_BASE_URL, "staff").queue(
            [self.prospect], "Subject", "<p>Body</p>", "", True
        )
        self.delivery = queued_mailing.deliveries[0]

    def test_the_task_sends_the_delivery(self) -> None:
        result = deliver_mail.apply(args=[str(self.delivery.pk)], throw=True)

        self.assertEqual(result.result, DeliveryStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryStatus.SENT)

    @override_settings(OUTREACH_DELIVERY_MAX_RETRIES=2)
    def test_transient_errors_are_retried_until_the_limit_then_fail(self) -> None:
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPServerDisconnected("down")
        ) as send:
            deliver_mail.apply(args=[str(self.delivery.pk)])

        self.assertEqual(send.call_count, 3)
        self.delivery.refresh_from_db()
        self.assertEqual((self.delivery.status, self.delivery.attempts), ("failed", 3))

    def test_a_permanent_error_is_not_retried(self) -> None:
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=RuntimeError("tag exploded")
        ) as send:
            deliver_mail.apply(args=[str(self.delivery.pk)])

        self.assertEqual(send.call_count, 1)
        self.assertEqual(MailingDelivery.objects.get().status, DeliveryStatus.FAILED)

    def test_an_unknown_delivery_is_ignored(self) -> None:
        result = deliver_mail.apply(args=[str(uuid.uuid4())], throw=True)

        self.assertIsNone(result.result)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(OUTREACH_BASE_URL=None)
    def test_the_task_needs_the_base_url(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            deliver_mail.apply(args=[str(self.delivery.pk)], throw=True)
