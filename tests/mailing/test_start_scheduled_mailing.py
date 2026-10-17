from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus, ProspectStatus, SkipReason
from outreach.services.scheduling import SchedulingUnavailable
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory


class StartScheduledMailingTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.first_prospect = ProspectFactory()
        self.second_prospect = ProspectFactory()
        self.mailing = self.scheduler.schedule(
            [self.first_prospect, self.second_prospect],
            "Subject",
            "<p>Body</p>",
            send_at=timezone.now() + timedelta(hours=2),
        ).mailing

    def test_starting_claims_the_recipients_and_queues_one_task_each(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            queued_count = self.scheduler.start(self.mailing)

        self.assertEqual(queued_count, 2)
        self.assertEqual(self.apply_async.call_count, 2)
        for delivery in self.mailing.deliveries.all():
            self.assertEqual(delivery.status, DeliveryStatus.PENDING)
        self.first_prospect.refresh_from_db()
        self.assertIsNotNone(self.first_prospect.last_mailed_at)

    def test_a_recipient_mailed_since_the_schedule_is_skipped_and_counted(self) -> None:
        self.second_prospect.last_mailed_at = timezone.now() - timedelta(seconds=1)
        self.second_prospect.save()

        with self.captureOnCommitCallbacks(execute=True):
            queued_count = self.scheduler.start(self.mailing)

        self.assertEqual(queued_count, 1)
        self.mailing.refresh_from_db()
        self.assertEqual(self.mailing.skipped_count, 1)
        self.assertEqual(self.mailing.skipped_reasons[SkipReason.COOLDOWN.value], 1)
        skipped_delivery = self.mailing.deliveries.get(prospect=self.second_prospect)
        self.assertEqual(skipped_delivery.status, DeliveryStatus.SKIPPED)
        self.assertEqual(self.apply_async.call_count, 1)

    def test_a_prospect_who_unsubscribed_since_the_schedule_is_skipped_at_delivery(
        self,
    ) -> None:
        self.first_prospect.status = ProspectStatus.UNSUBSCRIBED
        self.first_prospect.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.scheduler.start(self.mailing)

        delivery = self.mailing.deliveries.get(prospect=self.first_prospect)
        status = self.mailer.deliver(delivery.pk)

        self.assertEqual(status, DeliveryStatus.SKIPPED)

    def test_starting_again_does_nothing(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self.scheduler.start(self.mailing)
            queued_count = self.scheduler.start(self.mailing)

        self.assertEqual(queued_count, 0)
        self.assertEqual(self.apply_async.call_count, 2)

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_starting_is_refused_in_sync_mode(self) -> None:
        with self.assertRaises(SchedulingUnavailable):
            self.scheduler.start(self.mailing)

        self.assertEqual(
            set(self.mailing.deliveries.values_list("status", flat=True)),
            {DeliveryStatus.SCHEDULED},
        )
