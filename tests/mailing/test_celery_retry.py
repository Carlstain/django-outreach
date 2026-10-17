from smtplib import SMTPRecipientsRefused
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives

from outreach.choices import DeliveryStatus
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory


class CeleryRetryTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospect = ProspectFactory()
        with self.captureOnCommitCallbacks(execute=False):
            queued_mailing = self.mailer.queue(
                [self.prospect], "Subject", "<p>Body</p>", "", True
            )
        self.mailing = queued_mailing.mailing
        self.delivery = queued_mailing.deliveries[0]
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
        ):
            self.mailer.deliver(self.delivery.pk, may_retry=True)

    def test_the_reopened_delivery_is_queued_with_its_attempts_reset(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            report = self.mailer.retry(self.mailing)

        self.assertEqual(report.queued, [self.prospect])
        self.apply_async.assert_called_once()
        self.assertEqual(self.apply_async.call_args.kwargs["args"], [str(self.delivery.pk)])
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, DeliveryStatus.PENDING)
        self.assertEqual(self.delivery.attempts, 0)
