from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.models import MailingDelivery
from outreach.services.send_gate import SendGate
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=2)
class SendGateReleaseTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.now = timezone.now()
        self.mailing = MailingFactory()

    def create_waiting(self, count: int) -> list[MailingDelivery]:
        return [MailingDeliveryFactory(mailing=self.mailing) for _ in range(count)]

    def release_due(self, now=None):
        with self.captureOnCommitCallbacks(execute=True):
            return SendGate.release_due(now or self.now)

    def released_pks(self) -> set[str]:
        return {call.kwargs["args"][0] for call in self.apply_async.mock_calls}

    def test_releases_up_to_the_remaining_budget_in_creation_order(self) -> None:
        waiting = self.create_waiting(4)

        outcome = self.release_due()

        self.assertEqual(outcome.released, 2)
        self.assertEqual(self.released_pks(), {str(waiting[0].pk), str(waiting[1].pk)})
        for delivery in waiting[:2]:
            delivery.refresh_from_db()
            self.assertEqual(delivery.released_at, self.now)
        for delivery in waiting[2:]:
            delivery.refresh_from_db()
            self.assertIsNone(delivery.released_at)

    def test_second_run_releases_nothing_while_full(self) -> None:
        self.create_waiting(4)
        self.release_due()

        outcome = self.release_due()

        self.assertEqual(outcome.released, 0)
        self.assertEqual(self.apply_async.call_count, 2)
        self.assertEqual(MailingDelivery.objects.filter(released_at__isnull=False).count(), 2)

    def test_outcome_reports_waiting_and_next_run(self) -> None:
        self.create_waiting(3)

        outcome = self.release_due()

        self.assertEqual(outcome.waiting, 1)
        self.assertEqual(outcome.next_run_at, self.now + timedelta(hours=1))

    def test_next_run_is_none_when_nothing_waits(self) -> None:
        self.create_waiting(2)

        outcome = self.release_due()

        self.assertEqual(outcome.waiting, 0)
        self.assertIsNone(outcome.next_run_at)

    def test_nothing_waiting_releases_nothing(self) -> None:
        outcome = self.release_due()

        self.assertEqual(outcome.released, 0)
        self.assertIsNone(outcome.next_run_at)

    @override_settings(
        OUTREACH_SEND_LIMIT_PER_HOUR=None, OUTREACH_SEND_DELAY=timedelta(seconds=30)
    )
    def test_delay_releases_one_then_waits(self) -> None:
        self.create_waiting(3)

        first = self.release_due()
        too_early = self.release_due(self.now + timedelta(seconds=10))
        later = self.release_due(self.now + timedelta(seconds=31))

        self.assertEqual(first.released, 1)
        self.assertEqual(first.next_run_at, self.now + timedelta(seconds=30))
        self.assertEqual(too_early.released, 0)
        self.assertEqual(later.released, 1)
        self.assertEqual(later.next_run_at, self.now + timedelta(seconds=61))

    @override_settings(OUTREACH_SEND_DELAY=timedelta(seconds=30))
    def test_limit_and_delay_both_apply(self) -> None:
        self.create_waiting(4)

        first = self.release_due()
        second = self.release_due(self.now + timedelta(seconds=31))
        third = self.release_due(self.now + timedelta(seconds=62))

        self.assertEqual((first.released, second.released, third.released), (1, 1, 0))
        self.assertEqual(third.next_run_at, self.now + timedelta(hours=1))

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_removed_settings_release_every_waiting_delivery(self) -> None:
        self.create_waiting(3)

        outcome = self.release_due()

        self.assertEqual(outcome.released, 3)
        self.assertEqual(outcome.waiting, 0)

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_sync_mode_releases_every_waiting_delivery(self) -> None:
        self.create_waiting(3)

        self.assertEqual(self.release_due().released, 3)

    def test_only_pending_deliveries_without_a_release_are_released(self) -> None:
        MailingDeliveryFactory(mailing=self.mailing, status=DeliveryStatus.SCHEDULED)
        MailingDeliveryFactory(mailing=self.mailing, status=DeliveryStatus.FAILED)
        already_released = MailingDeliveryFactory(
            mailing=self.mailing, released_at=self.now - timedelta(days=1)
        )

        outcome = self.release_due()

        self.assertEqual(outcome.released, 0)
        already_released.refresh_from_db()
        self.assertEqual(already_released.released_at, self.now - timedelta(days=1))
        self.apply_async.assert_not_called()
