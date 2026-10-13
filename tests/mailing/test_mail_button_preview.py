from django.core import mail
from django.test import override_settings

from tests.base import MAIL_BASE_URL, OutreachMailTagTestCase
from tests.factories import (
    OUTREACH_PROSPECT_PERMISSIONS,
    OUTREACH_TEMPLATE_PERMISSIONS,
    EmailTemplateFactory,
    ProspectFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_emailtemplate_change_url, outreach_prospect_changelist_url


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailButtonPreviewTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(
            create_outreach_staff_user(
                [*OUTREACH_PROSPECT_PERMISSIONS, *OUTREACH_TEMPLATE_PERMISSIONS]
            )
        )

    def test_the_template_preview_shows_the_button_without_running_the_tag(self) -> None:
        calls: list[str] = []

        def booking_url(prospect: object) -> str:
            calls.append("called")
            return "https://real.example.org"

        self.register_tag(booking_url, "booking_url", example="Example link")
        template = EmailTemplateFactory(
            body_html=(
                '<p>{% button "Book" booking_url %} '
                '{% button "Docs" "https://example.org/docs" %}</p>'
            )
        )

        response = self.client.get(outreach_emailtemplate_change_url(str(template.pk)))

        preview_html = response.context["sample_preview_html"]
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="#"', preview_html)
        self.assertIn('href="https://example.org/docs"', preview_html)
        self.assertIn(">Book</a>", preview_html)
        self.assertNotIn("real.example.org", preview_html)
        self.assertEqual(calls, [])

    def test_the_compose_preview_shows_an_error_for_a_bad_computed_link(self) -> None:
        self.register_tag(lambda prospect: "", "booking_url")
        prospect = ProspectFactory()

        response = self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [str(prospect.pk)],
                "step": "preview",
                "is_newsletter": "on",
                "subject": "Hello",
                "body": '<p>{% button "Book" booking_url %}</p>',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outreach/admin/compose.html")
        self.assertIn("button 'Book'", response.context["form"].errors["body"][0])
        self.assertEqual(len(mail.outbox), 0)
