from django.contrib.messages import SUCCESS, get_messages

from outreach.choices import EventKind
from outreach.models import ProspectEvent
from tests.base import OutreachTestCase
from tests.factories import (
    AudienceFactory,
    ProspectFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_audience_add_url, outreach_prospect_changelist_url


class ProspectAudienceActionsTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user()
        self.client.force_login(self.staff_user)
        self.audience = AudienceFactory(name="Spring fair")

    def post_action(self, action: str, prospects: list, **extra_fields: str) -> object:
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": action,
                "_selected_action": [str(prospect.pk) for prospect in prospects],
                **extra_fields,
            },
        )

    def messages_of(self, response: object) -> list[tuple[int, str]]:
        return [
            (message.level, message.message) for message in get_messages(response.wsgi_request)
        ]

    def test_the_add_action_first_shows_the_audience_choice(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        response = self.post_action("add_to_audience", prospects)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outreach/admin/audience_choice.html")
        self.assertTrue(response.context["adding"])
        self.assertContains(response, "<h2>Add to an audience</h2>", html=True)
        self.assertEqual(response.context["selected_count"], 2)
        self.assertFalse(self.audience.prospects.exists())

    def test_applying_the_add_action_adds_the_selected_prospects(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        response = self.post_action(
            "add_to_audience", prospects, apply="1", audience=str(self.audience.pk)
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(self.audience.prospects.all()), set(prospects))
        self.assertEqual(
            self.messages_of(response), [(SUCCESS, "2 prospects added to Spring fair.")]
        )
        event = ProspectEvent.objects.filter(kind=EventKind.AUDIENCE_ADDED).first()
        self.assertEqual(event.actor, self.staff_user.get_username())

    def test_the_remove_action_shows_its_own_title(self) -> None:
        response = self.post_action("remove_from_audience", [ProspectFactory()])

        self.assertContains(response, "<h2>Remove from an audience</h2>", html=True)

    def test_applying_the_remove_action_removes_the_selected_prospects(self) -> None:
        member = ProspectFactory()
        staying = ProspectFactory()
        self.audience.prospects.add(member, staying)

        response = self.post_action(
            "remove_from_audience", [member], apply="1", audience=str(self.audience.pk)
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(self.audience.prospects.all()), [staying])
        self.assertEqual(
            self.messages_of(response), [(SUCCESS, "1 prospect removed from Spring fair.")]
        )

    def test_select_across_takes_every_prospect_of_the_current_filters(self) -> None:
        matching = [ProspectFactory(organization="Acme"), ProspectFactory(organization="Acme")]
        ProspectFactory(organization="Other")

        self.client.post(
            f"{outreach_prospect_changelist_url()}?q=Acme",
            {
                "action": "add_to_audience",
                "index": "0",
                "_selected_action": [str(matching[0].pk)],
                "select_across": "1",
                "apply": "1",
                "audience": str(self.audience.pk),
            },
        )

        self.assertEqual(set(self.audience.prospects.all()), set(matching))

    def test_the_choice_page_carries_the_selection_forward(self) -> None:
        prospect = ProspectFactory()

        response = self.post_action("add_to_audience", [prospect], select_across="1")

        self.assertContains(
            response, f'<input type="hidden" name="_selected_action" value="{prospect.pk}">'
        )
        self.assertContains(
            response, '<input type="hidden" name="action" value="add_to_audience">'
        )
        self.assertContains(response, '<input type="hidden" name="select_across" value="1">')

    def test_without_an_audience_the_page_offers_to_create_one(self) -> None:
        self.audience.delete()
        self.client.force_login(
            create_outreach_staff_user(["view_prospect", "change_prospect", "add_audience"])
        )

        response = self.post_action("add_to_audience", [ProspectFactory()])

        self.assertContains(response, "No audiences yet")
        self.assertContains(response, outreach_audience_add_url())

    def test_without_an_audience_and_without_the_add_permission_there_is_no_link(self) -> None:
        self.audience.delete()

        response = self.post_action("add_to_audience", [ProspectFactory()])

        self.assertContains(response, "No audiences yet")
        self.assertNotContains(response, outreach_audience_add_url())

    def test_view_only_staff_cannot_change_audience_members(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))
        prospect = ProspectFactory()

        for action in ("add_to_audience", "remove_from_audience"):
            self.post_action(action, [prospect], apply="1", audience=str(self.audience.pk))

        self.assertFalse(self.audience.prospects.exists())

    def test_the_prospect_page_shows_its_audiences_without_letting_them_be_edited(
        self,
    ) -> None:
        prospect = ProspectFactory()
        self.audience.prospects.add(prospect)

        response = self.client.get(
            f"{outreach_prospect_changelist_url()}{prospect.pk}/change/"
        )

        self.assertContains(response, "Spring fair")
        self.assertNotIn("audiences", response.context["adminform"].form.fields)

    def test_the_list_can_be_filtered_by_audience(self) -> None:
        member = ProspectFactory()
        ProspectFactory()
        self.audience.prospects.add(member)

        response = self.client.get(
            outreach_prospect_changelist_url(), {"audience": str(self.audience.pk)}
        )

        self.assertEqual(list(response.context["cl"].result_list), [member])
