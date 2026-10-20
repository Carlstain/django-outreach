from django.test import override_settings

from outreach.tasks import release_deliveries
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=1)
class ReleaseDeliveriesTaskTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailing = MailingFactory()

    def run_task(self) -> int:
        with self.captureOnCommitCallbacks(execute=True):
            return release_deliveries()

    def test_task_releases_and_reschedules_with_a_capped_countdown(self) -> None:
        for _ in range(2):
            MailingDeliveryFactory(mailing=self.mailing)

        released = self.run_task()

        self.assertEqual(released, 1)
        self.apply_async.assert_called_once()
        self.release_apply_async.assert_called_once_with(countdown=300, queue=None)

    @override_settings(OUTREACH_CELERY_QUEUE="outreach")
    def test_task_reschedules_on_the_configured_queue(self) -> None:
        for _ in range(2):
            MailingDeliveryFactory(mailing=self.mailing)

        self.run_task()

        self.release_apply_async.assert_called_once_with(countdown=300, queue="outreach")

    def test_task_does_not_reschedule_when_nothing_waits(self) -> None:
        MailingDeliveryFactory(mailing=self.mailing)

        self.run_task()

        self.release_apply_async.assert_not_called()

    def test_task_is_registered_under_its_name(self) -> None:
        self.assertEqual(release_deliveries.name, "outreach.release_deliveries")
