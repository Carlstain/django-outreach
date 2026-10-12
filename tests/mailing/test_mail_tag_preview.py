from tests.base import OutreachMailTagTestCase
from tests.factories import (
    OUTREACH_TEMPLATE_PERMISSIONS,
    EmailTemplateFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_emailtemplate_change_url


class MailTagPreviewTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(
            create_outreach_staff_user(["view_prospect", *OUTREACH_TEMPLATE_PERMISSIONS])
        )

    def test_the_template_preview_shows_the_example_and_never_runs_the_tag(self) -> None:
        calls: list[str] = []

        def tracked(prospect: object) -> str:
            calls.append("called")
            return "REAL"

        self.register_tag(tracked, "tracked", example="EXAMPLE VALUE")
        template = EmailTemplateFactory(
            subject="Subject {% tracked %}", body_html="<p>Body {% tracked %}</p>"
        )

        response = self.client.get(outreach_emailtemplate_change_url(str(template.pk)))

        self.assertEqual(response.status_code, 200)
        self.assertIn("EXAMPLE VALUE", response.context["sample_preview_html"])
        self.assertEqual(response.context["sample_preview_subject"], "Subject EXAMPLE VALUE")
        self.assertNotIn("REAL", response.context["sample_preview_html"])
        self.assertEqual(calls, [])
