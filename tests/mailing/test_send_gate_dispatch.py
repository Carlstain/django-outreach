from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.models import MailingDelivery
from outreach.services.send_gate import SendGate
from tests.base import CeleryMailTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory, ProspectFactory


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=2)
class SendGateDispatchTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospects = [ProspectFactory() for _ in range(5)]

    def send(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.mailer.send(self.prospects, "Subject", "<p>Body</p>")

    def release_due(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            SendGate.release_due()

    def test_send_hands_over_to_the_gate_and_queues_no_delivery(self) -> None:
        report = self.send()

        self.assertEqual(len(report.queued), 5)
        self.apply_async.assert_not_called()
        self.release_apply_async.assert_called_once_with(queue=None)

    def test_only_the_budget_is_queued_once_the_gate_releases(self) -> None:
        report = self.send()

        self.release_due()

        self.assertEqual(self.apply_async.call_count, 2)
        waiting = report.mailing.deliveries.filter(
            status=DeliveryStatus.PENDING, released_at__isnull=True
        )
        self.assertEqual(waiting.count(), 3)
        self.assertEqual(
            report.mailing.deliveries.filter(status=DeliveryStatus.FAILED).count(), 0
        )

    def test_nothing_is_failed_when_the_limit_is_full(self) -> None:
        other_mailing = MailingFactory()
        for _ in range(2):
            MailingDeliveryFactory(
                mailing=other_mailing, released_at=timezone.now() - timedelta(minutes=5)
            )
        report = self.send()

        self.release_due()

        self.apply_async.assert_not_called()
        self.assertEqual(
            report.mailing.deliveries.filter(status=DeliveryStatus.PENDING).count(), 5
        )
        self.assertEqual(
            MailingDelivery.objects.filter(status=DeliveryStatus.FAILED).count(), 0
        )

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_gate_off_queues_every_delivery_directly(self) -> None:
        self.send()

        self.assertEqual(self.apply_async.call_count, 5)
        self.release_apply_async.assert_not_called()

    @override_settings(OUTREACH_DISPATCH="sync", OUTREACH_SEND_LIMIT_PER_HOUR=1)
    def test_sync_mode_ignores_both_settings(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            report = self.mailer.send(self.prospects[:3], "Subject", "<p>Body</p>")

        self.assertEqual(len(report.sent), 3)
        self.assertEqual(len(mail.outbox), 3)
        self.release_apply_async.assert_not_called()
