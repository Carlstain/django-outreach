from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.services.send_gate import SendGate
from tests.base import OutreachTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory


@override_settings(OUTREACH_DISPATCH="celery", OUTREACH_SEND_LIMIT_PER_HOUR=3)
class SendGateUsageTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.now = timezone.now()
        self.mailing = MailingFactory()

    def release(self, minutes_ago: int, status: str = DeliveryStatus.SENT) -> None:
        MailingDeliveryFactory(
            mailing=self.mailing,
            status=status,
            released_at=self.now - timedelta(minutes=minutes_ago),
        )

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_none_without_a_limit(self) -> None:
        self.assertIsNone(SendGate.usage(self.now))

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_none_in_sync_mode(self) -> None:
        self.assertIsNone(SendGate.usage(self.now))

    def test_counts_only_the_last_hour(self) -> None:
        self.release(minutes_ago=59)
        self.release(minutes_ago=61)

        usage = SendGate.usage(self.now)

        self.assertEqual(usage.released, 1)
        self.assertEqual(usage.limit, 3)

    def test_counts_any_status(self) -> None:
        self.release(minutes_ago=5, status=DeliveryStatus.FAILED)

        self.assertEqual(SendGate.usage(self.now).released, 1)

    def test_free_at_is_when_the_oldest_counted_delivery_leaves_the_window(self) -> None:
        self.release(minutes_ago=50)
        self.release(minutes_ago=30)
        self.release(minutes_ago=10)

        usage = SendGate.usage(self.now)

        self.assertEqual(usage.free_at, self.now + timedelta(minutes=10))
        self.assertEqual(usage.remaining, 0)

    def test_free_at_is_none_when_not_full(self) -> None:
        self.release(minutes_ago=10)

        usage = SendGate.usage(self.now)

        self.assertIsNone(usage.free_at)
        self.assertEqual(usage.remaining, 2)

    def test_percent_is_released_over_limit(self) -> None:
        self.release(minutes_ago=10)

        self.assertEqual(SendGate.usage(self.now).percent, 33)
