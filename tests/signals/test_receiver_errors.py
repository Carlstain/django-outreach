from outreach.choices import ProspectStatus
from outreach.services.unsubscribe import ProspectUnsubscriber
from outreach.signals import prospect_unsubscribed
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory


class SignalReceiverErrorTests(OutreachTestCase):
    def test_a_failing_receiver_is_logged_and_does_not_break_the_unsubscribe(self) -> None:
        broken_receiver = self.connect_receiver(prospect_unsubscribed)
        broken_receiver.__qualname__ = "broken_receiver"
        broken_receiver.side_effect = RuntimeError("host receiver is broken")
        later_receiver = self.connect_receiver(prospect_unsubscribed)
        prospect = ProspectFactory()

        with (
            self.assertLogs("django.dispatch", level="ERROR"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            ProspectUnsubscriber().unsubscribe(prospect, "staff")

        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)
        later_receiver.assert_called_once()
