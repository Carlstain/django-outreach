from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=2)
class SendGateRetryTests(CeleryMailTestCase):
    def test_retry_resets_released_at_and_waits_under_a_full_limit(self) -> None:
        mailing = MailingFactory(failed_count=1)
        failed = MailingDeliveryFactory(
            mailing=mailing,
            status=DeliveryStatus.FAILED,
            released_at=timezone.now() - timedelta(hours=3),
        )
        for _ in range(2):
            MailingDeliveryFactory(
                mailing=MailingFactory(), released_at=timezone.now() - timedelta(minutes=5)
            )

        with self.captureOnCommitCallbacks(execute=True):
            report = self.mailer.retry(mailing)

        failed.refresh_from_db()
        self.assertEqual(failed.status, DeliveryStatus.PENDING)
        self.assertIsNone(failed.released_at)
        self.assertEqual(len(report.queued), 1)
        self.apply_async.assert_not_called()
        self.release_apply_async.assert_called_once_with(queue=None)
