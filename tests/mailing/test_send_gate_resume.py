from datetime import timedelta

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from outreach.models import MailingDelivery
from outreach.services.send_gate import SendGate
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=2)
class SendGateResumeTests(CeleryMailTestCase):
    def make_stale(self, *deliveries: MailingDelivery) -> None:
        MailingDelivery.objects.filter(pk__in=[delivery.pk for delivery in deliveries]).update(
            updated_at=timezone.now() - timedelta(hours=2)
        )

    def resume(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            call_command("outreach_resume_deliveries")

    def test_waiting_deliveries_are_kicked_not_enqueued(self) -> None:
        waiting = MailingDeliveryFactory()
        self.make_stale(waiting)

        self.resume()

        self.apply_async.assert_not_called()
        self.release_apply_async.assert_called_once_with(queue=None)

    def test_stale_released_deliveries_are_enqueued_again(self) -> None:
        released = MailingDeliveryFactory(released_at=timezone.now() - timedelta(hours=2))
        self.make_stale(released)

        self.resume()

        self.apply_async.assert_called_once()
        self.assertEqual(self.apply_async.call_args.kwargs["args"], [str(released.pk)])
        self.release_apply_async.assert_not_called()

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_gate_off_enqueues_every_stale_delivery(self) -> None:
        waiting = MailingDeliveryFactory()
        released = MailingDeliveryFactory(released_at=timezone.now() - timedelta(hours=2))
        self.make_stale(waiting, released)

        self.resume()

        self.assertEqual(self.apply_async.call_count, 2)
        self.release_apply_async.assert_not_called()

    def test_a_delivery_released_just_now_is_not_stale(self) -> None:
        waiting = MailingDeliveryFactory()
        self.make_stale(waiting)
        with self.captureOnCommitCallbacks(execute=True):
            SendGate.release_due()
        self.apply_async.reset_mock()

        self.resume()

        self.apply_async.assert_not_called()
