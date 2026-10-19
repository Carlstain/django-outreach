from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import override_settings

from outreach.choices import ACTOR_IMPORT, EventKind
from outreach.models import Audience, Prospect, ProspectEvent
from tests.base import OutreachTestCase
from tests.factories import AudienceFactory, ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_import_url, outreach_prospect_process_import_url

CSV_TEXT = "email,first_name\nnew@test.com,New\nkept@test.com,Kept\nnew@test.com,Again\n"


@override_settings(OUTREACH_LANGUAGE="en")
class ProspectImportAudienceTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user()
        self.client.force_login(self.staff_user)
        self.kept = ProspectFactory(email="kept@test.com")
        self.audience = AudienceFactory(name="Spring fair")

    def preview(self, csv_text: str = CSV_TEXT) -> HttpResponse:
        import_file = SimpleUploadedFile(
            "prospects.csv", csv_text.encode(), content_type="text/csv"
        )
        return self.client.post(outreach_prospect_import_url(), {"import_file": import_file})

    def confirm(
        self, csv_text: str = CSV_TEXT, lines: list[int] | None = None, **fields: str
    ) -> HttpResponse:
        preview_response = self.preview(csv_text)
        posted = {**preview_response.context["confirm_form"].initial, **fields}
        if lines is None:
            lines = sorted(preview_response.context["checked_lines"])
        return self.client.post(
            outreach_prospect_process_import_url(), {**posted, "audience_lines": lines}
        )

    def test_the_preview_ticks_every_row_but_the_repeated_one(self) -> None:
        response = self.preview()

        self.assertEqual(response.context["checked_lines"], {2, 3})
        self.assertContains(response, 'name="audience_lines"', count=2)

    def test_every_ticked_row_joins_the_chosen_audience(self) -> None:
        self.confirm(audience=str(self.audience.pk))

        self.assertEqual(
            set(self.audience.prospects.values_list("email", flat=True)),
            {"new@test.com", "kept@test.com"},
        )

    def test_an_unticked_row_does_not_join(self) -> None:
        self.confirm(lines=[2], audience=str(self.audience.pk))

        self.assertEqual(
            list(self.audience.prospects.values_list("email", flat=True)), ["new@test.com"]
        )
        self.assertTrue(Prospect.objects.filter(email="kept@test.com").exists())

    def test_a_new_audience_name_creates_the_audience_with_its_author(self) -> None:
        self.confirm(new_audience_name="Autumn fair")

        audience = Audience.objects.get(name="Autumn fair")
        self.assertEqual(audience.created_by, self.staff_user)
        self.assertEqual(audience.prospects.count(), 2)

    def test_a_name_that_exists_ignoring_case_imports_nothing(self) -> None:
        response = self.confirm(new_audience_name="spring FAIR")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["confirm_form"].errors["new_audience_name"],
            ["An audience with this name already exists."],
        )
        self.assertFalse(Prospect.objects.filter(email="new@test.com").exists())
        self.assertEqual(Audience.objects.count(), 1)

    def test_an_audience_and_a_new_name_together_import_nothing(self) -> None:
        response = self.confirm(
            audience=str(self.audience.pk), new_audience_name="Autumn fair"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Prospect.objects.filter(email="new@test.com").exists())

    def test_a_file_of_existing_rows_still_fills_the_audience(self) -> None:
        response = self.preview("email\nkept@test.com\n")

        self.assertContains(response, "Confirm import")

        self.confirm("email\nkept@test.com\n", audience=str(self.audience.pk))

        self.assertEqual(list(self.audience.prospects.all()), [self.kept])

    def test_audience_events_are_recorded_by_the_import_for_new_members_only(self) -> None:
        self.audience.prospects.add(self.kept)

        self.confirm(audience=str(self.audience.pk))

        events = ProspectEvent.objects.filter(kind=EventKind.AUDIENCE_ADDED)
        self.assertEqual(
            list(events.values_list("prospect__email", "actor", "detail")),
            [("new@test.com", ACTOR_IMPORT, "Spring fair")],
        )

    def test_without_an_audience_the_import_is_unchanged(self) -> None:
        self.confirm()

        self.assertTrue(Prospect.objects.filter(email="new@test.com").exists())
        self.assertFalse(self.audience.prospects.exists())

    def test_staff_without_change_permission_get_no_audience_choice(self) -> None:
        self.client.force_login(create_outreach_staff_user(["add_prospect", "view_prospect"]))

        response = self.preview()

        self.assertNotContains(response, 'name="audience_lines"')
        self.assertNotContains(response, "new_audience_name")

    def test_a_posted_audience_without_change_permission_is_refused(self) -> None:
        self.client.force_login(create_outreach_staff_user(["add_prospect", "view_prospect"]))
        preview_response = self.preview()

        response = self.client.post(
            outreach_prospect_process_import_url(),
            {
                **preview_response.context["confirm_form"].initial,
                "audience": str(self.audience.pk),
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Prospect.objects.filter(email="new@test.com").exists())
