from unittest.mock import patch

from django.contrib.messages import SUCCESS, get_messages

from outreach.choices import EventKind
from outreach.forms import AudienceChoiceForm
from outreach.models import Audience, ProspectEvent
from outreach.services.audiences import AudienceMembers
from tests.base import OutreachTestCase
from tests.factories import (
    AudienceFactory,
    ProspectFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_prospect_changelist_url


class ProspectAudienceActionsTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user()
        self.client.force_login(self.staff_user)
        self.audience = AudienceFactory(name="Spring fair")

    def post_action(
        self, action: str, prospects: list, url: str | None = None, **extra_fields: str
    ) -> object:
        return self.client.post(
            url or outreach_prospect_changelist_url(),
            {
                "action": action,
                "_selected_action": [str(prospect.pk) for prospect in prospects],
                **extra_fields,
            },
        )

    def assert_name_clash_refused(self, response: object) -> None:
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].errors["new_audience_name"],
            ["An audience with this name already exists."],
        )
        self.assertEqual(Audience.objects.count(), 1)
        self.assertFalse(self.audience.prospects.exists())

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

        self.post_action(
            "add_to_audience",
            [matching[0]],
            url=f"{outreach_prospect_changelist_url()}?q=Acme",
            index="0",
            select_across="1",
            apply="1",
            audience=str(self.audience.pk),
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

    def test_the_add_page_offers_a_new_name_next_to_the_existing_audiences(self) -> None:
        response = self.post_action("add_to_audience", [ProspectFactory()])

        self.assertContains(response, '<select name="audience"', html=False)
        self.assertContains(response, 'name="new_audience_name"')
        self.assertContains(
            response, "Creates the audience and adds the selected prospects to it."
        )

    def test_typing_a_name_creates_the_audience_and_adds_the_selected_prospects(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        response = self.post_action(
            "add_to_audience", prospects, apply="1", new_audience_name="  Autumn fair  "
        )

        self.assertEqual(response.status_code, 302)
        created = Audience.objects.get(name="Autumn fair")
        self.assertEqual((created.created_by, created.updated_by), (self.staff_user,) * 2)
        self.assertEqual(set(created.prospects.all()), set(prospects))
        self.assertEqual(
            self.messages_of(response),
            [
                (SUCCESS, "The audience Autumn fair was created."),
                (SUCCESS, "2 prospects added to Autumn fair."),
            ],
        )
        self.assertEqual(
            ProspectEvent.objects.filter(kind=EventKind.AUDIENCE_ADDED).count(), 2
        )

    def test_a_new_audience_can_take_every_prospect_of_the_current_filters(self) -> None:
        matching = [ProspectFactory(organization="Acme"), ProspectFactory(organization="Acme")]
        ProspectFactory(organization="Other")

        self.post_action(
            "add_to_audience",
            [matching[0]],
            url=f"{outreach_prospect_changelist_url()}?q=Acme",
            index="0",
            select_across="1",
            apply="1",
            new_audience_name="Acme contacts",
        )

        self.assertEqual(
            set(Audience.objects.get(name="Acme contacts").prospects.all()), set(matching)
        )

    def test_without_an_audience_the_add_page_asks_only_for_a_name(self) -> None:
        self.audience.delete()

        response = self.post_action("add_to_audience", [ProspectFactory()])

        self.assertContains(response, 'name="new_audience_name"')
        self.assertNotContains(response, '<select name="audience"')
        self.assertNotContains(response, "No audiences yet")

    def test_without_an_audience_a_name_creates_the_first_one(self) -> None:
        self.audience.delete()
        prospect = ProspectFactory()

        self.post_action(
            "add_to_audience", [prospect], apply="1", new_audience_name="Spring fair"
        )

        self.assertEqual(list(Audience.objects.get().prospects.all()), [prospect])

    def test_a_name_that_exists_is_refused_and_nothing_is_added(self) -> None:
        prospect = ProspectFactory()

        response = self.post_action(
            "add_to_audience", [prospect], apply="1", new_audience_name="spring FAIR"
        )

        self.assert_name_clash_refused(response)
        self.assertContains(response, "An audience with this name already exists.")

    def test_choosing_an_audience_and_typing_a_name_is_refused(self) -> None:
        response = self.post_action(
            "add_to_audience",
            [ProspectFactory()],
            apply="1",
            audience=str(self.audience.pk),
            new_audience_name="Autumn fair",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose an audience or type a new name, not both.")
        self.assertEqual(Audience.objects.count(), 1)
        self.assertFalse(self.audience.prospects.exists())

    def test_choosing_nothing_is_refused(self) -> None:
        response = self.post_action("add_to_audience", [ProspectFactory()], apply="1")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose an audience, or type the name of a new one.")
        self.assertEqual(Audience.objects.count(), 1)

    def test_a_name_taken_in_the_meantime_is_a_form_error_not_a_server_error(self) -> None:
        def skip_the_clash_check(form: AudienceChoiceForm) -> str:
            return form.cleaned_data["new_audience_name"]

        with patch.object(AudienceChoiceForm, "clean_new_audience_name", skip_the_clash_check):
            response = self.post_action(
                "add_to_audience",
                [ProspectFactory()],
                apply="1",
                new_audience_name="SPRING fair",
            )

        self.assert_name_clash_refused(response)

    def test_a_failure_while_adding_does_not_leave_the_new_audience_behind(self) -> None:
        with (
            patch.object(AudienceMembers, "add", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            self.post_action(
                "add_to_audience",
                [ProspectFactory()],
                apply="1",
                new_audience_name="Autumn fair",
            )

        self.assertFalse(Audience.objects.filter(name="Autumn fair").exists())

    def test_the_remove_page_has_no_name_box(self) -> None:
        response = self.post_action("remove_from_audience", [ProspectFactory()])

        self.assertContains(response, '<select name="audience"')
        self.assertNotContains(response, "new_audience_name")

    def test_removing_with_no_audience_says_there_is_nothing_to_remove_from(self) -> None:
        self.audience.delete()

        response = self.post_action("remove_from_audience", [ProspectFactory()])

        self.assertContains(response, "No audiences yet")
        self.assertContains(response, "There is nothing to remove the prospects from.")

    def test_a_name_cannot_be_used_to_create_an_audience_when_removing(self) -> None:
        member = ProspectFactory()
        self.audience.prospects.add(member)

        self.post_action(
            "remove_from_audience", [member], apply="1", new_audience_name="Autumn fair"
        )

        self.assertEqual(Audience.objects.count(), 1)
        self.assertTrue(self.audience.prospects.filter(pk=member.pk).exists())

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
