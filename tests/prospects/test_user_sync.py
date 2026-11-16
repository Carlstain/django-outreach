from typing import Any

from django.core.checks import Error, Warning
from django.core.management import call_command
from django.test import override_settings

from outreach.checks import check_sync_users
from outreach.choices import ACTOR_SYSTEM, EventKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent
from outreach.services.unsubscribe import SuppressionList
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, UserFactory

HOOK_PATH = "tests.prospects.test_user_sync"
CREATE = override_settings(OUTREACH_SYNC_USERS="create")
LINK = override_settings(OUTREACH_SYNC_USERS="link")


def refuse_everyone(user: Any) -> bool:
    return False


def fail(user: Any) -> bool:
    raise RuntimeError("boom")


def company_fields(user: Any) -> dict[str, str]:
    return {"organization": "Acme"}


def sees_committed_user(user: Any) -> bool:
    return type(user).objects.filter(pk=user.pk).exists()


class UserSyncTestCase(OutreachTestCase):
    def create_user(self, **fields: Any) -> Any:
        with self.captureOnCommitCallbacks(execute=True):
            return UserFactory(**fields)


class SyncOffTests(UserSyncTestCase):
    def test_nothing_happens_by_default(self) -> None:
        prospect = ProspectFactory(email="jane@test.com")

        self.create_user(email="jane@test.com")
        self.create_user(email="other@test.com")

        prospect.refresh_from_db()
        self.assertIsNone(prospect.user)
        self.assertEqual(Prospect.objects.count(), 1)


@LINK
class LinkModeTests(UserSyncTestCase):
    def test_links_a_matching_prospect(self) -> None:
        prospect = ProspectFactory(email="jane@test.com")

        user = self.create_user(email="jane@test.com")

        prospect.refresh_from_db()
        self.assertEqual(prospect.user, user)
        event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.LINKED)
        self.assertEqual(event.actor, ACTOR_SYSTEM)

    def test_creates_no_prospect(self) -> None:
        self.create_user(email="new@test.com")

        self.assertEqual(Prospect.objects.count(), 0)

    def test_leaves_a_prospect_linked_to_another_user_alone(self) -> None:
        prospect = ProspectFactory(email="shared@test.com")
        other_user = UserFactory(email="other@test.com")
        Prospect.objects.filter(pk=prospect.pk).update(user=other_user)

        self.create_user(email="shared@test.com")

        prospect.refresh_from_db()
        self.assertEqual(prospect.user, other_user)


@CREATE
class CreateModeTests(UserSyncTestCase):
    def test_creates_a_linked_prospect_for_a_new_user(self) -> None:
        user = self.create_user(email="New@Test.com")

        prospect = Prospect.objects.get(email="new@test.com")
        self.assertEqual(prospect.user, user)
        event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.ADDED)
        self.assertEqual((event.actor, event.detail), (ACTOR_SYSTEM, "user sync"))

    def test_links_a_matching_prospect_without_a_duplicate(self) -> None:
        prospect = ProspectFactory(email="jane@test.com")

        user = self.create_user(email="jane@test.com")

        prospect.refresh_from_db()
        self.assertEqual(prospect.user, user)
        self.assertEqual(Prospect.objects.count(), 1)

    def test_inactive_user_is_not_created_but_is_linked(self) -> None:
        self.create_user(email="inactive@test.com", is_active=False)
        prospect = ProspectFactory(email="match@test.com")

        user = self.create_user(email="match@test.com", is_active=False)

        self.assertFalse(Prospect.objects.filter(email="inactive@test.com").exists())
        prospect.refresh_from_db()
        self.assertEqual(prospect.user, user)

    def test_suppressed_address_is_created_unsubscribed(self) -> None:
        SuppressionList().add("gone@test.com")

        self.create_user(email="gone@test.com")

        prospect = Prospect.objects.get(email="gone@test.com")
        self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)

    @override_settings(OUTREACH_USER_PROSPECT_FIELDS=f"{HOOK_PATH}.company_fields")
    def test_applies_the_prospect_fields_hook(self) -> None:
        self.create_user(email="corp@test.com")

        self.assertEqual(Prospect.objects.get(email="corp@test.com").organization, "Acme")

    def test_updating_a_user_does_nothing(self) -> None:
        with override_settings(OUTREACH_SYNC_USERS=False):
            user = self.create_user(email="before@test.com")

        with self.captureOnCommitCallbacks(execute=True):
            user.email = "after@test.com"
            user.save()

        self.assertEqual(Prospect.objects.count(), 0)

    def test_raw_saves_are_skipped(self) -> None:
        from outreach.receivers import sync_new_user

        user = UserFactory.build(email="raw@test.com")

        with self.captureOnCommitCallbacks(execute=True):
            sync_new_user(type(user), user, created=True, raw=True)

        self.assertEqual(Prospect.objects.count(), 0)


@CREATE
class FilterTests(UserSyncTestCase):
    @override_settings(OUTREACH_SYNC_USERS_FILTER=f"{HOOK_PATH}.refuse_everyone")
    def test_a_refusing_filter_blocks_creation_but_not_linking(self) -> None:
        prospect = ProspectFactory(email="jane@test.com")

        user = self.create_user(email="jane@test.com")
        self.create_user(email="refused@test.com")

        prospect.refresh_from_db()
        self.assertEqual(prospect.user, user)
        self.assertFalse(Prospect.objects.filter(email="refused@test.com").exists())

    @override_settings(OUTREACH_SYNC_USERS_FILTER=f"{HOOK_PATH}.fail")
    def test_a_failing_filter_creates_nothing_and_logs_no_address(self) -> None:
        with self.assertLogs("outreach", level="ERROR") as logs:
            self.create_user(email="secret.person@test.com")

        self.assertEqual(Prospect.objects.count(), 0)
        self.assertNotIn("secret.person", "\n".join(logs.output))

    @override_settings(OUTREACH_SYNC_USERS_FILTER=f"{HOOK_PATH}.sees_committed_user")
    def test_the_filter_runs_after_commit(self) -> None:
        self.create_user(email="first@test.com")

        self.assertEqual(Prospect.objects.count(), 1)


class SyncUsersChecksTests(OutreachTestCase):
    def test_default_has_no_messages(self) -> None:
        self.assertEqual(check_sync_users(None), [])

    @override_settings(OUTREACH_SYNC_USERS="everything")
    def test_unknown_mode_is_an_error(self) -> None:
        self.assertEqual([message.id for message in check_sync_users(None)], ["outreach.E007"])

    @CREATE
    @override_settings(OUTREACH_SYNC_USERS_FILTER="no.such.module.hook")
    def test_unimportable_filter_is_an_error(self) -> None:
        messages = check_sync_users(None)

        self.assertEqual([message.id for message in messages], ["outreach.E008"])
        self.assertIsInstance(messages[0], Error)

    @override_settings(OUTREACH_SYNC_USERS_FILTER=f"{HOOK_PATH}.refuse_everyone")
    def test_filter_without_create_mode_is_a_warning(self) -> None:
        messages = check_sync_users(None)

        self.assertEqual([message.id for message in messages], ["outreach.W002"])
        self.assertIsInstance(messages[0], Warning)


@CREATE
class LoadCommandStillWorksTests(UserSyncTestCase):
    def test_load_command_after_sync_finds_nothing_to_create(self) -> None:
        self.create_user(email="synced@test.com")

        call_command("outreach_load_users")

        self.assertEqual(Prospect.objects.count(), 1)
