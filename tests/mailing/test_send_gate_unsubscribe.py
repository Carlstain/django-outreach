from django.test import override_settings

from outreach.choices import DeliveryStatus, ProspectStatus
from outreach.services.send_gate import SendGate
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=2)
class SendGateUnsubscribeTests(CeleryMailTestCase):
    def test_waiting_prospect_who_unsubscribes_is_skipped_on_release(self) -> None:
        stays, leaves = ProspectFactory(), ProspectFactory()
        queued_mailing = self.mailer.queue([stays, leaves], "Subject", "<p>Body</p>", "", True)
        leaves_delivery = queued_mailing.deliveries[1]
        leaves.status = ProspectStatus.UNSUBSCRIBED
        leaves.save(update_fields=["status"])

        with self.captureOnCommitCallbacks(execute=True):
            SendGate.release_due()
        status = self.mailer.deliver(leaves_delivery.pk)

        leaves_delivery.refresh_from_db()
        self.assertIsNotNone(leaves_delivery.released_at)
        self.assertEqual(status, DeliveryStatus.SKIPPED)
        queued_mailing.mailing.refresh_from_db()
        self.assertEqual(queued_mailing.mailing.skipped_count, 1)
        self.assertEqual(queued_mailing.mailing.failed_count, 0)
