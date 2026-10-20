from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.services.scheduling import MailingScheduler
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=1)
class SendGateScheduledStartTests(CeleryMailTestCase):
    def test_start_goes_through_the_gate(self) -> None:
        mailing = MailingFactory(scheduled_for=timezone.now() - timedelta(minutes=1))
        scheduled = MailingDeliveryFactory(mailing=mailing, status=DeliveryStatus.SCHEDULED)
        MailingDeliveryFactory(
            mailing=MailingFactory(), released_at=timezone.now() - timedelta(minutes=5)
        )

        with self.captureOnCommitCallbacks(execute=True):
            started = MailingScheduler.start(mailing)

        scheduled.refresh_from_db()
        self.assertEqual(started, 1)
        self.assertEqual(scheduled.status, DeliveryStatus.PENDING)
        self.assertIsNone(scheduled.released_at)
        self.apply_async.assert_not_called()
        self.release_apply_async.assert_called_once_with(queue=None)
