from django.core.exceptions import ValidationError

from outreach.choices import ACTOR_SYSTEM, EventKind, ProspectKind, ProspectStatus
from outreach.models import ProspectEvent
from outreach.services.subscription import ProspectSubscriptions
from outreach.services.unsubscribe import SuppressionList
from outreach.signals import prospect_subscribed
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, UserFactory


class ProspectSubscriptionTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.subscriptions = ProspectSubscriptions()
        self.receiver = self.connect_receiver(prospect_subscribed)

    def test_a_new_prospect_is_created_with_an_event_and_a_signal_after_commit(self) -> None:
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            result = self.subscriptions.subscribe(
                "  New.Person@Example.org ",
                consent_source="footer form",
                first_name="Nora",
                organization="Acme",
                kind=ProspectKind.ORGANIZATION,
            )

        self.assertTrue(result.created)
        self.assertEqual(result.prospect.email, "new.person@example.org")
        self.assertEqual(result.prospect.first_name, "Nora")
        self.assertEqual(result.prospect.kind, ProspectKind.ORGANIZATION)
        event = ProspectEvent.objects.get(prospect=result.prospect, kind=EventKind.SUBSCRIBED)
        self.assertEqual(event.detail, "footer form")
        self.assertEqual(event.actor, ACTOR_SYSTEM)
        self.receiver.assert_not_called()
        for callback in callbacks:
            callback()
        self.receiver.assert_called_once()
        arguments = self.receiver.call_args.kwargs
        self.assertEqual(arguments["prospect"], result.prospect)
        self.assertEqual(arguments["consent_source"], "footer form")

    def test_an_existing_prospect_is_returned_unchanged_without_event_or_signal(self) -> None:
        prospect = ProspectFactory(first_name="Ada")

        with self.captureOnCommitCallbacks(execute=True):
            result = self.subscriptions.subscribe(
                prospect.email.upper(), consent_source="footer form", first_name="Other"
            )

        self.assertFalse(result.created)
        self.assertEqual(result.prospect, prospect)
        prospect.refresh_from_db()
        self.assertEqual(prospect.first_name, "Ada")
        self.assertFalse(ProspectEvent.objects.filter(kind=EventKind.SUBSCRIBED).exists())
        self.receiver.assert_not_called()

    def test_an_unsubscribed_prospect_stays_unsubscribed(self) -> None:
        prospect = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)

        result = self.subscriptions.subscribe(prospect.email, consent_source="footer form")

        self.assertFalse(result.created)
        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)

    def test_a_suppressed_address_is_created_unsubscribed_without_a_signal(self) -> None:
        SuppressionList().add("gone@example.org")

        with self.captureOnCommitCallbacks(execute=True):
            result = self.subscriptions.subscribe("gone@example.org", consent_source="form")

        self.assertTrue(result.created)
        self.assertEqual(result.prospect.status, ProspectStatus.UNSUBSCRIBED)
        self.assertTrue(
            ProspectEvent.objects.filter(
                prospect=result.prospect, kind=EventKind.SUBSCRIBED
            ).exists()
        )
        self.receiver.assert_not_called()

    def test_a_matching_user_is_linked(self) -> None:
        user = UserFactory(email="member@example.org")

        result = self.subscriptions.subscribe("member@example.org", consent_source="form")

        self.assertEqual(result.prospect.user, user)

    def test_an_empty_consent_source_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.subscriptions.subscribe("someone@example.org", consent_source="  ")

    def test_an_invalid_address_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            self.subscriptions.subscribe("not an address", consent_source="form")
