from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import override_settings

from outreach.models import Prospect
from tests.base import OutreachTestCase
from tests.factories import create_outreach_staff_user
from tests.routes import outreach_prospect_import_url

CSV_CONTENT = "Email\nada@test.com\n"
CSV_SIZE = len(CSV_CONTENT.encode())


@override_settings(OUTREACH_LANGUAGE="en")
class ProspectImportSizeLimitTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())

    def upload_csv(self) -> HttpResponse:
        import_file = SimpleUploadedFile(
            "prospects.csv", CSV_CONTENT.encode(), content_type="text/csv"
        )
        return self.client.post(outreach_prospect_import_url(), {"import_file": import_file})

    @override_settings(OUTREACH_MAX_IMPORT_BYTES=CSV_SIZE - 1)
    def test_a_file_over_the_limit_is_rejected(self) -> None:
        response = self.upload_csv()

        self.assertContains(response, f"the limit is {CSV_SIZE - 1}.")
        self.assertNotIn("confirm_form", response.context)
        self.assertFalse(Prospect.objects.exists())

    @override_settings(OUTREACH_MAX_IMPORT_BYTES=CSV_SIZE)
    def test_a_file_at_the_limit_is_accepted(self) -> None:
        response = self.upload_csv()

        self.assertIn("confirm_form", response.context)
