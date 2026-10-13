from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import override_settings

from outreach.choices import (
    ACTOR_IMPORT,
    EventKind,
    ImportRowStatus,
    ProspectKind,
    ProspectStatus,
)
from outreach.models import Prospect, ProspectEvent
from outreach.services.prospect_csv import ProspectCsvColumns
from outreach.services.unsubscribe import SuppressionList
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import (
    outreach_prospect_changelist_url,
    outreach_prospect_import_url,
    outreach_prospect_process_import_url,
)

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

    def upload_csv(
        self, csv_content: bytes | str, file_name: str = "prospects.csv"
    ) -> HttpResponse:
        if isinstance(csv_content, str):
            csv_content = csv_content.encode()
        import_file = SimpleUploadedFile(file_name, csv_content, content_type="text/csv")
        return self.client.post(outreach_prospect_import_url(), {"import_file": import_file})

    def import_csv(
        self, csv_content: bytes | str, file_name: str = "prospects.csv"
    ) -> HttpResponse:
        preview_response = self.upload_csv(csv_content, file_name)
        self.assertIn("confirm_form", preview_response.context)
        confirm_form = preview_response.context["confirm_form"]
        return self.client.post(outreach_prospect_process_import_url(), confirm_form.initial)

    def test_configured_header_aliases_map_to_prospect_fields(self) -> None:
        response = self.import_csv(
            "Email,Given_name,Surname,Company,Category\n"
            "Ada@Test.com,Ada,Lovelace,Analytical Engines,organization\n",
            file_name="members.csv",
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
        self.assertEqual(imported_event.detail, "members.csv")

    def test_city_and_country_aliases_are_mapped(self) -> None:
        self.import_csv("Email,Town,Nation\nada@test.com,Springfield,Freedonia\n")

        prospect = Prospect.objects.get(email="ada@test.com")
        self.assertEqual(prospect.city, "Springfield")
        self.assertEqual(prospect.country, "Freedonia")

    def test_a_blank_kind_means_individual(self) -> None:
        self.import_csv("email,kind\nada@test.com,\n")

        self.assertEqual(Prospect.objects.get().kind, ProspectKind.INDIVIDUAL)

    def test_a_byte_order_mark_and_surrounding_spaces_are_ignored(self) -> None:
        self.import_csv("﻿ Email ,First_name\n Ada@Test.com , Ada \n".encode())

        prospect = Prospect.objects.get()
        self.assertEqual((prospect.email, prospect.first_name), ("ada@test.com", "Ada"))

    def test_unknown_columns_are_ignored(self) -> None:
        self.import_csv("email,favourite_colour\nada@test.com,green\n")

        self.assertEqual(Prospect.objects.get().email, "ada@test.com")

    def test_rows_for_existing_emails_are_skipped(self) -> None:
        existing = ProspectFactory(email="same@test.com", first_name="Original")

        response = self.import_csv(
            "email,first_name\nsame@test.com,Changed\nnew@test.com,Fresh\n"
        )

        existing.refresh_from_db()
        self.assertEqual(existing.first_name, "Original")
        self.assertEqual(Prospect.objects.count(), 2)
        self.assertTrue(Prospect.objects.filter(email="new@test.com").exists())
        self.assertEqual(
            [message.message for message in get_messages(response.wsgi_request)],
            ["1 prospect imported. 1 row skipped."],
        )

    def test_an_email_repeated_in_the_file_is_imported_once(self) -> None:
        self.import_csv("email,first_name\nada@test.com,First\nADA@test.com,Second\n")

        self.assertEqual(Prospect.objects.get().first_name, "First")

    def test_suppressed_address_is_imported_as_unsubscribed(self) -> None:
        SuppressionList().add("blocked@test.com")

        self.import_csv("email,first_name\nblocked@test.com,Blocked\n")

        prospect = Prospect.objects.get(email="blocked@test.com")
        self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)

    def test_the_preview_saves_nothing_and_marks_new_and_skipped_rows(self) -> None:
        ProspectFactory(email="same@test.com")

        response = self.upload_csv("email\nsame@test.com\nnew@test.com\n")

        statuses = [row.status for row in response.context["preview"].rows]
        self.assertEqual(statuses, [ImportRowStatus.SKIPPED, ImportRowStatus.NEW])
        self.assertEqual(Prospect.objects.count(), 1)

    def test_a_preview_of_only_existing_rows_offers_no_confirmation(self) -> None:
        ProspectFactory(email="same@test.com")

        response = self.upload_csv("email\nsame@test.com\n")

        self.assertContains(response, "nothing to import")
        self.assertNotContains(response, "Confirm import")

    @override_settings(OUTREACH_MAX_IMPORT_ROWS=2)
    def test_file_over_the_row_limit_is_rejected(self) -> None:
        response = self.upload_csv("email\none@test.com\ntwo@test.com\nthree@test.com\n")

        self.assertNotIn("confirm_form", response.context)
        self.assertContains(response, "The file has 3 rows, the limit is 2.")
        self.assertEqual(Prospect.objects.count(), 0)

    def test_one_bad_row_blocks_the_whole_file(self) -> None:
        response = self.upload_csv("email\ngood@test.com\nnot-an-email\nalso@test.com\n")

        invalid_rows = response.context["preview"].invalid_rows
        self.assertEqual([row.line for row in invalid_rows], [3])
        self.assertNotIn("confirm_form", response.context)
        self.assertEqual(Prospect.objects.count(), 0)

    def test_a_row_without_an_email_is_invalid(self) -> None:
        response = self.upload_csv("email,first_name\n,Nobody\n")

        self.assertEqual(len(response.context["preview"].invalid_rows), 1)

    def test_an_unknown_kind_is_invalid(self) -> None:
        response = self.upload_csv("email,kind\nada@test.com,alien\n")

        self.assertEqual(len(response.context["preview"].invalid_rows), 1)

    def test_a_file_without_an_email_column_is_rejected(self) -> None:
        response = self.upload_csv("first_name\nAda\n")

        self.assertContains(response, "The file has no email column.")

    def test_an_empty_file_is_rejected(self) -> None:
        response = self.upload_csv("\n")

        self.assertContains(response, "The file is empty.")

    def test_a_file_that_is_not_utf8_is_rejected(self) -> None:
        response = self.upload_csv("email\nrené@test.com\n".encode("latin-1"))

        self.assertContains(response, "The file must be UTF-8 text.")
        self.assertEqual(Prospect.objects.count(), 0)

    def test_confirm_step_with_a_bad_row_rolls_the_whole_file_back(self) -> None:
        preview_response = self.upload_csv("email\ngood@test.com\nalso@test.com\n")
        confirm_fields = {
            **preview_response.context["confirm_form"].initial,
            "csv_text": "email\ngood@test.com\nnot-an-email\n",
        }

        response = self.client.post(outreach_prospect_process_import_url(), confirm_fields)

        self.assertEqual(len(response.context["preview"].invalid_rows), 1)
        self.assertEqual(Prospect.objects.count(), 0)

    def test_confirm_step_without_a_file_goes_back_to_the_import_page(self) -> None:
        response = self.client.post(outreach_prospect_process_import_url(), {})

        self.assertRedirects(
            response, outreach_prospect_import_url(), fetch_redirect_response=False
        )

    def test_view_only_staff_cannot_import(self) -> None:
        self.client.force_login(
            create_outreach_staff_user(permission_codenames=["view_prospect"])
        )

        import_page = self.client.get(outreach_prospect_import_url())
        confirm_response = self.client.post(outreach_prospect_process_import_url(), {})

        self.assertEqual(import_page.status_code, 403)
        self.assertEqual(confirm_response.status_code, 403)

    def test_import_columns_reflect_every_header_alias(self) -> None:
        aliases_by_column = {
            column["name"]: column["aliases"] for column in ProspectCsvColumns().with_aliases()
        }

        for alias, field_name in HEADER_ALIASES.items():
            self.assertIn(alias, aliases_by_column[field_name])
