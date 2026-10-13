from datetime import timedelta

from django.test import override_settings

from outreach.services.variables import MailVariables
from tests.base import OutreachTestCase
from tests.factories import create_outreach_staff_user
from tests.routes import outreach_help_url

SECTION_ANCHORS = [
    "h-templates",
    "h-audiences",
    "h-overview",
    "h-import",
    "h-search",
    "h-send",
    "h-variables",
    "h-skipped",
    "h-unsub",
    "h-mailings",
    "h-perms",
    "h-trouble",
]


@override_settings(OUTREACH_LANGUAGE="en")
class HelpPageTests(OutreachTestCase):
    def test_anonymous_user_is_redirected_to_login(self) -> None:
        response = self.client.get(outreach_help_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_staff_without_view_permission_is_redirected_to_login(self) -> None:
        self.client.force_login(create_outreach_staff_user(permission_codenames=[]))

        response = self.client.get(outreach_help_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_staff_with_view_permission_sees_the_page(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

        response = self.client.get(outreach_help_url())

        self.assertEqual(response.status_code, 200)

    def test_page_lists_every_mail_variable(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

        response = self.client.get(outreach_help_url())

        for variable in MailVariables().catalog():
            self.assertContains(response, f"<code>{{{{ {variable.key} }}}}</code>", html=True)

    @override_settings(
        OUTREACH_MAX_RECIPIENTS_PER_SEND=37, OUTREACH_RESEND_COOLDOWN=timedelta(hours=53)
    )
    def test_page_shows_the_configured_cap_and_cooldown(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

        response = self.client.get(outreach_help_url())

        self.assertContains(
            response, "<li>Prospects mailed within the last 53 hours.</li>", html=True
        )
        self.assertContains(
            response,
            "<li>Anyone past the first 37 recipients of one send. "
            "Send again later for the rest.</li>",
            html=True,
        )

    def test_page_has_every_section_anchor(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

        response = self.client.get(outreach_help_url())

        for anchor in SECTION_ANCHORS:
            self.assertContains(response, f'id="{anchor}"')

    def test_permissions_table_has_separate_rows_for_prospects_and_mailings(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

        response = self.client.get(outreach_help_url())

        self.assertContains(
            response,
            "<tr><td>View prospects</td><td>Open Outreach and read prospects.</td></tr>",
            html=True,
        )
        self.assertContains(
            response,
            "<tr><td>View mailings</td><td>Read the Mailings log.</td></tr>",
            html=True,
        )

    def test_templates_section_and_permission_rows_are_present(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

        response = self.client.get(outreach_help_url())

        self.assertContains(response, 'id="h-templates"')
        for permission_label in (
            "View templates",
            "Add templates",
            "Change templates",
            "Delete templates",
        ):
            self.assertRegex(
                response.content.decode(),
                rf"<tr><td>{permission_label}</td><td>[^<]+</td></tr>",
            )
