import csv
import io

from django.http import HttpResponse
from django.test import override_settings

from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url

EXPORT_ACTION = "export_csv"


@override_settings(OUTREACH_LANGUAGE="en")
class ProspectExportTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(
            create_outreach_staff_user(permission_codenames=["view_prospect"])
        )

    def export(self, prospects: list, **extra_fields: str) -> HttpResponse:
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": EXPORT_ACTION,
                "_selected_action": [str(prospect.pk) for prospect in prospects],
                **extra_fields,
            },
        )

    def exported_rows(self, response: HttpResponse) -> list[list[str]]:
        return list(csv.reader(io.StringIO(response.content.decode())))

    def test_the_export_is_a_csv_download(self) -> None:
        response = self.export([ProspectFactory()])

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"], 'attachment; filename="prospects.csv"'
        )

    def test_export_headers_use_the_translated_field_labels(self) -> None:
        response = self.export([ProspectFactory()])

        self.assertEqual(
            self.exported_rows(response)[0],
            ["Email", "First name", "Last name", "Organization", "City", "Country", "Kind"],
        )

    def test_export_includes_city_and_country_columns(self) -> None:
        prospect = ProspectFactory(city="Springfield", country="Freedonia")

        headers, row = self.exported_rows(self.export([prospect]))

        exported = dict(zip(headers, row, strict=True))
        self.assertEqual(exported["City"], "Springfield")
        self.assertEqual(exported["Country"], "Freedonia")
        self.assertEqual(exported["Kind"], "individual")

    def test_only_the_selected_prospects_are_exported(self) -> None:
        selected = ProspectFactory()
        ProspectFactory()

        rows = self.exported_rows(self.export([selected]))

        self.assertEqual([row[0] for row in rows[1:]], [selected.email])

    def test_select_across_exports_every_prospect(self) -> None:
        prospects = [ProspectFactory() for _ in range(3)]

        rows = self.exported_rows(self.export(prospects[:1], select_across="1"))

        self.assertEqual(len(rows) - 1, len(prospects))

    def test_cells_that_start_a_spreadsheet_formula_are_escaped(self) -> None:
        for formula in ("=SUM(1+1)", "+1", "-1", "@SUM(1)", "\tTab"):
            with self.subTest(formula=formula):
                prospect = ProspectFactory(first_name=formula)

                row = self.exported_rows(self.export([prospect]))[1]

                self.assertEqual(row[1], f"'{formula}")

    def test_a_plain_cell_is_left_alone(self) -> None:
        prospect = ProspectFactory(first_name="Ada")

        self.assertEqual(self.exported_rows(self.export([prospect]))[1][1], "Ada")

    def test_staff_without_view_permission_cannot_export(self) -> None:
        self.client.force_login(create_outreach_staff_user(permission_codenames=[]))

        response = self.export([ProspectFactory()])

        self.assertNotEqual(response.get("Content-Type"), "text/csv; charset=utf-8")
