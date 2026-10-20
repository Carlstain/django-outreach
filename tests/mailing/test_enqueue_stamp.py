from datetime import timedelta

from django.utils import timezone

from outreach.services.mailing import ProspectMailer
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory


class EnqueueStampTests(CeleryMailTestCase):
    def test_enqueue_sets_released_at_on_unreleased_deliveries(self) -> None:
        delivery = MailingDeliveryFactory()

        with self.captureOnCommitCallbacks(execute=True):
            ProspectMailer.enqueue([delivery.pk])

        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.released_at)
        self.apply_async.assert_called_once()

    def test_enqueue_keeps_an_existing_released_at(self) -> None:
        released_at = timezone.now() - timedelta(minutes=20)
        delivery = MailingDeliveryFactory(released_at=released_at)

        with self.captureOnCommitCallbacks(execute=True):
            ProspectMailer.enqueue([delivery.pk])

        delivery.refresh_from_db()
        self.assertEqual(delivery.released_at, released_at)
        self.apply_async.assert_called_once()

    def test_enqueue_uses_the_given_release_time(self) -> None:
        released_at = timezone.now() - timedelta(minutes=5)
        delivery = MailingDeliveryFactory()

        with self.captureOnCommitCallbacks(execute=True):
            ProspectMailer.enqueue([delivery.pk], released_at=released_at)

        delivery.refresh_from_db()
        self.assertEqual(delivery.released_at, released_at)
