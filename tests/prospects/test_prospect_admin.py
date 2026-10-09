from django.core import mail
from django.test import override_settings
from django.urls import reverse

from outreach.choices import EventKind, ProspectKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent, Suppression
from outreach.services.unsubscribe import SuppressionList
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, UserFactory, create_outreach_staff_user
from tests.routes import (
    outreach_prospect_add_url,
    outreach_prospect_change_url,
    outreach_prospect_changelist_url,
    outreach_prospect_delete_url,
)


class ProspectAdminTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user()
        self.client.force_login(self.staff_user)

    def test_changelist_lists_prospects(self) -> None:
        prospect = ProspectFactory()

        response = self.client.get(outreach_prospect_changelist_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cl"].result_list), [prospect])

    def test_search_matches_email_and_names(self) -> None:
        by_email = ProspectFactory(email="findme@test.com")
        by_name = ProspectFactory(last_name="Zhivago")
        ProspectFactory()

        email_response = self.client.get(outreach_prospect_changelist_url(), {"q": "findme"})
        name_response = self.client.get(outreach_prospect_changelist_url(), {"q": "zhivago"})

        self.assertEqual(list(email_response.context["cl"].result_list), [by_email])
        self.assertEqual(list(name_response.context["cl"].result_list), [by_name])

    def test_filters_by_status_kind_and_membership(self) -> None:
        contacted = ProspectFactory(status=ProspectStatus.CONTACTED)
        organization = ProspectFactory(kind=ProspectKind.ORGANIZATION)
        member = ProspectFactory(user=UserFactory())
        url = outreach_prospect_changelist_url()

        by_status = self.client.get(url, {"status__exact": ProspectStatus.CONTACTED})
        by_kind = self.client.get(url, {"kind__exact": ProspectKind.ORGANIZATION})
        members_only = self.client.get(url, {"member": "yes"})
        non_members = self.client.get(url, {"member": "no"})

        self.assertEqual(list(by_status.context["cl"].result_list), [contacted])
        self.assertEqual(list(by_kind.context["cl"].result_list), [organization])
        self.assertEqual(list(members_only.context["cl"].result_list), [member])
        self.assertCountEqual(non_members.context["cl"].result_list, [contacted, organization])

    def test_add_creates_prospect_with_added_event(self) -> None:
        response = self.client.post(
            outreach_prospect_add_url(),
            {"email": "  New@Test.com ", "kind": ProspectKind.INDIVIDUAL},
        )

        self.assertEqual(response.status_code, 302)
        prospect = Prospect.objects.get(email="new@test.com")
        added_event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.ADDED)
        self.assertEqual(added_event.actor, self.staff_user.get_username())

    def test_change_updates_names_but_never_the_email(self) -> None:
        prospect = ProspectFactory(email="original@test.com")

        response = self.client.post(
            outreach_prospect_change_url(prospect.pk),
            {
                "email": "other@test.com",
                "kind": ProspectKind.INDIVIDUAL,
                "first_name": "Grace",
                "last_name": "Hopper",
                "organization": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        prospect.refresh_from_db()
        self.assertEqual(prospect.email, "original@test.com")
        self.assertEqual(prospect.first_name, "Grace")
        self.assertTrue(
            ProspectEvent.objects.filter(prospect=prospect, kind=EventKind.EDITED).exists()
        )

    def test_delete_keeps_the_suppression(self) -> None:
        prospect = ProspectFactory(email="gone@test.com")
        SuppressionList().add(prospect.email)

        response = self.client.post(outreach_prospect_delete_url(prospect.pk), {"post": "yes"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Prospect.objects.filter(pk=prospect.pk).exists())
        self.assertEqual(Suppression.objects.count(), 1)
        self.assertTrue(SuppressionList().contains("gone@test.com"))

    def test_anonymous_user_is_redirected_to_login(self) -> None:
        self.client.logout()

        response = self.client.get(outreach_prospect_changelist_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_staff_without_view_permission_is_refused(self) -> None:
        self.client.force_login(create_outreach_staff_user(permission_codenames=[]))

        response = self.client.get(outreach_prospect_changelist_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_default_admin_still_renders(self) -> None:
        superuser = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(superuser)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def post_action(self, action: str, prospects: list) -> object:
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": action,
                "_selected_action": [str(prospect.pk) for prospect in prospects],
            },
        )

    def test_unsubscribe_selected_unsubscribes_suppresses_and_records_events(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        self.post_action("unsubscribe_selected", prospects)

        for prospect in prospects:
            prospect.refresh_from_db()
            self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)
            self.assertTrue(SuppressionList().contains(prospect.email))
            event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.UNSUBSCRIBED)
            self.assertEqual(event.actor, self.staff_user.get_username())

    def test_view_only_staff_cannot_run_the_change_actions(self) -> None:
        self.client.force_login(
            create_outreach_staff_user(permission_codenames=["view_prospect"])
        )
        prospect = ProspectFactory()
        UserFactory(email=prospect.email)

        for action in ("send_mail", "unsubscribe_selected", "link_users"):
            self.post_action(action, [prospect])

        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.PROSPECT)
        self.assertIsNone(prospect.user)
        self.assertFalse(Suppression.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(OUTREACH_LANGUAGE="fr")
    def test_prospect_form_labels_have_no_colon_suffix(self) -> None:
        response = self.client.get(outreach_prospect_add_url())

        for bound_field in response.context["adminform"].form:
            self.assertNotRegex(str(bound_field.label_tag()), r":\s*</label>")

    def test_initials_follow_the_display_name(self) -> None:
        individual = ProspectFactory.build(first_name="Ada", last_name="Lovelace")
        organization = ProspectFactory.build(
            first_name="", last_name="", organization="Acme Dynamics & Sons"
        )
        email_only = ProspectFactory.build(
            first_name="", last_name="", organization="", email="zed@test.com"
        )

        self.assertEqual(individual.initials, "AL")
        self.assertEqual(organization.initials, "AD")
        self.assertEqual(email_only.initials, "ZE")
