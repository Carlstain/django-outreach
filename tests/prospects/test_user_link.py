from outreach.choices import ACTOR_SYSTEM, EventKind
from outreach.models import Prospect, ProspectEvent
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, UserFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url


class UserLinkTests(OutreachTestCase):
    def test_prospect_is_linked_to_user_with_same_email_ignoring_case(self) -> None:
        user = UserFactory(email="jane@test.com")

        prospect = ProspectFactory(email="Jane@Test.com")

        prospect.refresh_from_db()
        self.assertEqual(prospect.user, user)

    def test_prospect_without_matching_user_stays_unlinked(self) -> None:
        UserFactory(email="someone.else@test.com")

        prospect = ProspectFactory(email="jane@test.com")

        self.assertIsNone(prospect.user)

    def test_prospect_with_several_matching_users_stays_unlinked(self) -> None:
        UserFactory(email="jane@test.com")
        UserFactory(email="JANE@test.com")

        prospect = ProspectFactory(email="jane@test.com")

        self.assertIsNone(prospect.user)

    def test_user_who_already_has_a_prospect_is_not_linked_again(self) -> None:
        user = UserFactory(email="jane@test.com")
        first_prospect = ProspectFactory(email="other.address@test.com", user=user)

        second_prospect = ProspectFactory(email="JANE@test.com")

        self.assertEqual(first_prospect.user, user)
        self.assertIsNone(second_prospect.user)

    def test_link_action_links_prospects_created_before_the_account(self) -> None:
        linkable = ProspectFactory(email="late@test.com")
        unmatched = ProspectFactory(email="never@test.com")
        user = UserFactory(email="late@test.com")
        self.client.force_login(create_outreach_staff_user())

        response = self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "link_users",
                "_selected_action": [str(linkable.pk), str(unmatched.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        linkable.refresh_from_db()
        unmatched.refresh_from_db()
        self.assertEqual(linkable.user, user)
        self.assertIsNone(unmatched.user)
        linked_event = ProspectEvent.objects.get(prospect=linkable, kind=EventKind.LINKED)
        self.assertEqual(linked_event.actor, ACTOR_SYSTEM)
        self.assertFalse(
            ProspectEvent.objects.filter(prospect=unmatched, kind=EventKind.LINKED).exists()
        )
        self.assertEqual(Prospect.objects.filter(user__isnull=False).count(), 1)
