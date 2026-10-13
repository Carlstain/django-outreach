from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import override_settings

from outreach.models import Prospect
from outreach.services.prospect_csv import ProspectCsvColumns
from tests.base import OutreachTestCase
from tests.factories import create_outreach_staff_user
from tests.routes import (
    outreach_help_url,
    outreach_prospect_import_url,
    outreach_prospect_process_import_url,
)

ALIASED_CSV = (
    "email,given_name,surname,employer\nada@test.com,Ada,Lovelace,Analytical Engines\n"
)


@override_settings(OUTREACH_LANGUAGE="en")
class ImportAliasesSettingTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())

    def import_csv(self, csv_content: str) -> HttpResponse:
        import_file = SimpleUploadedFile(
            "prospects.csv", csv_content.encode(), content_type="text/csv"
        )
        preview_response = self.client.post(
            outreach_prospect_import_url(), {"import_file": import_file}
        )
        confirm_form = preview_response.context["confirm_form"]
        return self.client.post(outreach_prospect_process_import_url(), confirm_form.initial)

    def test_without_the_setting_aliased_headers_are_not_mapped(self) -> None:
        self.import_csv(ALIASED_CSV)

        prospect = Prospect.objects.get(email="ada@test.com")
        self.assertEqual(prospect.first_name, "")
        self.assertEqual(prospect.last_name, "")
        self.assertEqual(prospect.organization, "")

    def test_without_the_setting_no_column_lists_aliases(self) -> None:
        self.assertEqual(
            [column["aliases"] for column in ProspectCsvColumns().with_aliases()],
            [[]] * len(ProspectCsvColumns().with_aliases()),
        )

    def test_without_the_setting_the_help_page_shows_no_other_headers(self) -> None:
        response = self.client.get(outreach_help_url())

        self.assertContains(
            response, "<tr><td><code>first_name</code></td><td>-</td></tr>", html=True
        )

    @override_settings(
        OUTREACH_IMPORT_HEADER_ALIASES={
            "given_name": "first_name",
            "surname": "last_name",
            "employer": "organization",
        }
    )
    def test_configured_aliases_are_honoured_by_the_import(self) -> None:
        self.import_csv(ALIASED_CSV)

        prospect = Prospect.objects.get(email="ada@test.com")
        self.assertEqual(prospect.first_name, "Ada")
        self.assertEqual(prospect.last_name, "Lovelace")
        self.assertEqual(prospect.organization, "Analytical Engines")

    @override_settings(
        OUTREACH_IMPORT_HEADER_ALIASES={"given_name": "first_name", "given": "first_name"}
    )
    def test_configured_aliases_are_listed_on_the_help_page(self) -> None:
        response = self.client.get(outreach_help_url())

        self.assertContains(
            response,
            "<tr><td><code>first_name</code></td>"
            "<td><code>given_name</code> <code>given</code></td></tr>",
            html=True,
        )
        self.assertContains(
            response, "<tr><td><code>last_name</code></td><td>-</td></tr>", html=True
        )

    @override_settings(OUTREACH_IMPORT_HEADER_ALIASES={"GIVEN_NAME": "first_name"})
    def test_import_columns_lists_the_configured_aliases(self) -> None:
        columns = {
            column["name"]: column["aliases"] for column in ProspectCsvColumns().with_aliases()
        }

        self.assertEqual(columns["first_name"], ["GIVEN_NAME"])
        self.assertEqual(columns["email"], [])
