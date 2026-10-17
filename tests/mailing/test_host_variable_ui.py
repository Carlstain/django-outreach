from unittest.mock import patch

from django.apps import apps
from django.test import override_settings

from outreach.models import Prospect
from outreach.widgets import TrixWidget
from tests.base import OutreachMailTagTestCase
from tests.factories import EmailTemplateFactory, create_outreach_staff_user
from tests.routes import outreach_emailtemplate_change_url, outreach_help_url


@override_settings(OUTREACH_LANGUAGE="en")
class HostVariableUiTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.calls: list[Prospect] = []

        def plan_name(prospect: Prospect) -> str:
            self.calls.append(prospect)
            raise AssertionError("a preview must never run host code")

        self.register_variable(plan_name, "plan_name", example="Pro plan")

    def test_the_editor_menu_lists_the_variable_with_its_example(self) -> None:
        html = TrixWidget().render("body", "")

        self.assertIn('data-trix-variable="plan_name"', html)
        self.assertIn("Pro plan", html)

    def test_the_help_page_lists_the_variable(self) -> None:
        self.client.force_login(create_outreach_staff_user())

        response = self.client.get(outreach_help_url())

        self.assertContains(response, "plan_name")
        self.assertContains(response, "Pro plan")

    def test_the_template_preview_shows_the_example_and_never_runs_the_function(self) -> None:
        self.client.force_login(
            create_outreach_staff_user(
                ["view_prospect", "view_emailtemplate", "change_emailtemplate"]
            )
        )
        template = EmailTemplateFactory(
            subject="Your {{ plan_name }} plan", body_html="<p>{{ plan_name }}</p>"
        )

        response = self.client.get(outreach_emailtemplate_change_url(template.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your Pro plan plan")
        self.assertEqual(self.calls, [])


class MailVariableAutodiscoveryTests(OutreachMailTagTestCase):
    def test_the_app_looks_for_a_mail_variables_module(self) -> None:
        with patch("outreach.apps.autodiscover_modules") as autodiscover:
            apps.get_app_config("outreach").ready()

        autodiscover.assert_any_call("mail_variables")
        autodiscover.assert_any_call("mail_tags")
