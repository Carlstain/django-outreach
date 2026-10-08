from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import override_settings
from import_export.formats.base_formats import CSV
from import_export.tmp_storages import TempFolderStorage

from outreach.choices import ACTOR_IMPORT, EventKind, ProspectKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent
from outreach.resources import ProspectResource, import_columns
from outreach.services.unsubscribe import SuppressionList
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import (
    outreach_prospect_changelist_url,
    outreach_prospect_import_url,
    outreach_prospect_process_import_url,
)

CSV_FORMAT_INDEX = "0"
HEADER_ALIASES = {
    "given_name": "first_name",
    "surname": "last_name",
    "company": "organization",
    "category": "kind",
    "town": "city",
    "nation": "country",
}


@override_settings(OUTREACH_LANGUAGE="en", OUTREACH_IMPORT_HEADER_ALIASES=HEADER_ALIASES)
class ProspectImportTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())

    def upload_csv(self, csv_content: str) -> HttpResponse:
        import_file = SimpleUploadedFile(
            "prospects.csv", csv_content.encode(), content_type="text/csv"
        )
        return self.client.post(
            outreach_prospect_import_url(),
            {"import_file": import_file, "format": CSV_FORMAT_INDEX},
        )

    def import_csv(self, csv_content: str) -> HttpResponse:
        preview_response = self.upload_csv(csv_content)
        self.assertIn("confirm_form", preview_response.context)
        confirm_form = preview_response.context["confirm_form"]
        return self.client.post(outreach_prospect_process_import_url(), confirm_form.initial)

    def test_configured_header_aliases_map_to_prospect_fields(self) -> None:
        response = self.import_csv(
            "Email,Given_name,Surname,Company,Category\n"
            "Ada@Test.com,Ada,Lovelace,Analytical Engines,organization\n"
        )

        self.assertRedirects(
            response, outreach_prospect_changelist_url(), fetch_redirect_response=False
        )
        prospect = Prospect.objects.get(email="ada@test.com")
        self.assertEqual(prospect.first_name, "Ada")
        self.assertEqual(prospect.last_name, "Lovelace")
        self.assertEqual(prospect.organization, "Analytical Engines")
        self.assertEqual(prospect.kind, ProspectKind.ORGANIZATION)
        imported_event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.IMPORTED)
        self.assertEqual(imported_event.actor, ACTOR_IMPORT)

    def test_city_and_country_aliases_are_mapped(self) -> None:
        self.import_csv("Email,Town,Nation\nada@test.com,Springfield,Freedonia\n")

        prospect = Prospect.objects.get(email="ada@test.com")
        self.assertEqual(prospect.city, "Springfield")
        self.assertEqual(prospect.country, "Freedonia")

    def test_rows_for_existing_emails_are_skipped(self) -> None:
        existing = ProspectFactory(email="same@test.com", first_name="Original")

        self.import_csv("email,first_name\nsame@test.com,Changed\nnew@test.com,Fresh\n")

        existing.refresh_from_db()
        self.assertEqual(existing.first_name, "Original")
        self.assertEqual(Prospect.objects.count(), 2)
        self.assertTrue(Prospect.objects.filter(email="new@test.com").exists())

    def test_suppressed_address_is_imported_as_unsubscribed(self) -> None:
        SuppressionList().add("blocked@test.com")

        self.import_csv("email,first_name\nblocked@test.com,Blocked\n")

        prospect = Prospect.objects.get(email="blocked@test.com")
        self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)

    @override_settings(OUTREACH_MAX_IMPORT_ROWS=2)
    def test_file_over_the_row_limit_is_rejected(self) -> None:
        response = self.upload_csv("email\none@test.com\ntwo@test.com\nthree@test.com\n")

        self.assertNotIn("confirm_form", response.context)
        self.assertEqual(Prospect.objects.count(), 0)

    def test_one_bad_row_blocks_the_whole_file(self) -> None:
        response = self.upload_csv("email\ngood@test.com\nnot-an-email\nalso@test.com\n")

        self.assertNotIn("confirm_form", response.context)
        self.assertEqual(Prospect.objects.count(), 0)

    def test_export_headers_use_the_translated_field_labels(self) -> None:
        ProspectFactory()

        exported = ProspectResource().export()

        self.assertEqual(
            exported.headers,
            ["Email", "First name", "Last name", "Organization", "City", "Country", "Kind"],
        )

    def test_export_includes_city_and_country_columns(self) -> None:
        ProspectFactory(city="Springfield", country="Freedonia")

        exported = ProspectResource().export()

        self.assertIn("City", exported.headers)
        self.assertIn("Country", exported.headers)
        row = dict(zip(exported.headers, exported[0], strict=True))
        self.assertEqual(row["City"], "Springfield")
        self.assertEqual(row["Country"], "Freedonia")

    def test_export_escapes_cells_starting_with_an_equals_sign(self) -> None:
        ProspectFactory(first_name="=SUM(1+1)")

        exported_csv = CSV().export_data(ProspectResource().export())

        self.assertNotIn("=SUM", exported_csv)
        self.assertIn("SUM(1+1)", exported_csv)

    def test_confirm_step_with_a_bad_row_rolls_the_whole_file_back(self) -> None:
        preview_response = self.upload_csv("email\ngood@test.com\nalso@test.com\n")
        confirm_initial = preview_response.context["confirm_form"].initial
        TempFolderStorage(name=confirm_initial["import_file_name"]).save(
            "email\ngood@test.com\nnot-an-email\n"
        )

        self.client.post(outreach_prospect_process_import_url(), confirm_initial)

        self.assertEqual(Prospect.objects.count(), 0)

    def test_view_only_staff_cannot_import(self) -> None:
        self.client.force_login(
            create_outreach_staff_user(permission_codenames=["view_prospect"])
        )

        import_page = self.client.get(outreach_prospect_import_url())
        confirm_response = self.client.post(outreach_prospect_process_import_url(), {})

        self.assertEqual(import_page.status_code, 403)
        self.assertEqual(confirm_response.status_code, 403)

    def test_import_columns_reflect_every_header_alias(self) -> None:
        aliases_by_column = {column["name"]: column["aliases"] for column in import_columns()}

        for alias, field_name in HEADER_ALIASES.items():
            self.assertIn(alias, aliases_by_column[field_name])
