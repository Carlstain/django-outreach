from outreach.choices import ProspectStatus
from outreach.services.unsubscribe import ProspectUnsubscriber
from outreach.signals import prospect_unsubscribed
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory


class UnsubscribeSignalTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospect = ProspectFactory()
        self.receiver = self.connect_receiver(prospect_unsubscribed)

    def test_the_signal_is_sent_after_commit_with_the_prospect_and_the_actor(self) -> None:
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            ProspectUnsubscriber().unsubscribe(self.prospect, "staff")

        self.receiver.assert_not_called()
        for callback in callbacks:
            callback()
        self.receiver.assert_called_once()
        arguments = self.receiver.call_args.kwargs
        self.assertEqual(arguments["sender"], ProspectUnsubscriber)
        self.assertEqual(arguments["prospect"], self.prospect)
        self.assertEqual(arguments["actor"], "staff")

    def test_unsubscribing_again_sends_nothing_more(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            ProspectUnsubscriber().unsubscribe(self.prospect, "staff")
            ProspectUnsubscriber().unsubscribe(self.prospect, "staff")

        self.receiver.assert_called_once()
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.status, ProspectStatus.UNSUBSCRIBED)
