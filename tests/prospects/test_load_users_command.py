from io import StringIO
from typing import Any

from django.core.management import CommandError, call_command
from django.test import override_settings

from outreach.choices import ACTOR_SYSTEM, EventKind, ProspectKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent
from outreach.services.unsubscribe import SuppressionList
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, UserFactory

HOOK_PATH = "tests.prospects.test_load_users_command"


def company_fields(user: Any) -> dict[str, str]:
    return {"kind": ProspectKind.ORGANIZATION, "organization": "Acme", "city": "Lyon"}


def forbidden_fields(user: Any) -> dict[str, str]:
    return {"status": ProspectStatus.CONTACTED}


def invalid_kind_fields(user: Any) -> dict[str, str]:
    return {"kind": "robot"}


class LoadUsersCommandTests(OutreachTestCase):
    def run_command(self, *arguments: str) -> str:
        output = StringIO()
        call_command("outreach_load_users", *arguments, stdout=output)
        return output.getvalue()

    def test_dry_run_writes_nothing_and_prints_counts(self) -> None:
        UserFactory.create_batch(2)

        output = self.run_command("--dry-run")

        self.assertEqual(Prospect.objects.count(), 0)
        self.assertEqual(ProspectEvent.objects.count(), 0)
        self.assertIn("Prospects created: 2", output)

    def test_output_never_contains_an_address(self) -> None:
        UserFactory(email="secret.person@test.com")

        output = self.run_command()

        self.assertNotIn("secret.person", output)

    def test_creates_linked_prospects_with_names(self) -> None:
        user = UserFactory(email="Jane@Test.com", first_name="Jane", last_name="Doe")

        self.run_command()

        prospect = Prospect.objects.get()
        self.assertEqual(prospect.email, "jane@test.com")
        self.assertEqual(prospect.user, user)
        self.assertEqual((prospect.first_name, prospect.last_name), ("Jane", "Doe"))

    def test_second_run_creates_nothing(self) -> None:
        UserFactory.create_batch(2)
        self.run_command()

        output = self.run_command()

        self.assertEqual(Prospect.objects.count(), 2)
        self.assertEqual(ProspectEvent.objects.count(), 2)
        self.assertIn("Prospects created: 0", output)
        self.assertIn("Already prospects: 2", output)

    def test_inactive_users_are_skipped_unless_included(self) -> None:
        UserFactory(is_active=False)

        self.run_command()
        self.assertEqual(Prospect.objects.count(), 0)

        self.run_command("--include-inactive")
        self.assertEqual(Prospect.objects.count(), 1)

    def test_users_without_email_are_skipped(self) -> None:
        UserFactory(email="")

        self.run_command()

        self.assertEqual(Prospect.objects.count(), 0)

    def test_suppressed_address_is_created_unsubscribed(self) -> None:
        UserFactory(email="gone@test.com")
        SuppressionList().add("gone@test.com")

        output = self.run_command()

        self.assertEqual(Prospect.objects.get().status, ProspectStatus.UNSUBSCRIBED)
        self.assertIn("unsubscribed: 1", output)

    def test_existing_prospect_is_left_untouched(self) -> None:
        user = UserFactory(email="known@test.com", first_name="New")
        existing = ProspectFactory(
            email="known@test.com", first_name="Old", status=ProspectStatus.UNSUBSCRIBED
        )

        self.run_command()

        existing.refresh_from_db()
        self.assertEqual(existing.first_name, "Old")
        self.assertEqual(existing.status, ProspectStatus.UNSUBSCRIBED)
        self.assertEqual(existing.user, user)
        self.assertEqual(ProspectEvent.objects.count(), 0)

    def test_user_already_linked_under_another_address_is_not_duplicated(self) -> None:
        user = UserFactory(email="account@test.com")
        ProspectFactory(email="other@test.com", user=user)

        self.run_command()

        self.assertEqual(Prospect.objects.count(), 1)

    def test_addresses_differing_by_case_give_one_prospect(self) -> None:
        UserFactory(username="first", email="Same@test.com")
        UserFactory(username="second", email="same@test.com")

        self.run_command()

        self.assertEqual(Prospect.objects.count(), 1)

    def test_records_an_added_event_by_the_system(self) -> None:
        UserFactory()

        self.run_command()

        event = ProspectEvent.objects.get()
        self.assertEqual(event.kind, EventKind.ADDED)
        self.assertEqual(event.actor, ACTOR_SYSTEM)

    @override_settings(OUTREACH_USER_PROSPECT_FIELDS=f"{HOOK_PATH}.company_fields")
    def test_hook_fills_host_specific_fields(self) -> None:
        UserFactory()

        self.run_command()

        prospect = Prospect.objects.get()
        self.assertEqual(prospect.kind, ProspectKind.ORGANIZATION)
        self.assertEqual(prospect.organization, "Acme")
        self.assertEqual(prospect.city, "Lyon")

    @override_settings(OUTREACH_USER_PROSPECT_FIELDS=f"{HOOK_PATH}.forbidden_fields")
    def test_hook_returning_a_field_it_may_not_set_is_refused(self) -> None:
        UserFactory()

        with self.assertRaises(CommandError):
            self.run_command()

        self.assertEqual(Prospect.objects.count(), 0)

    @override_settings(OUTREACH_USER_PROSPECT_FIELDS=f"{HOOK_PATH}.invalid_kind_fields")
    def test_invalid_hook_value_counts_the_user_as_invalid(self) -> None:
        UserFactory()

        output = self.run_command()

        self.assertEqual(Prospect.objects.count(), 0)
        self.assertIn("Invalid: 1", output)
