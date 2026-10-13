from django.test import override_settings

from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", OUTREACH_SITE_NAME="Acme Club"
)
class MailHeaderTextTests(OutreachTestCase):
    def render_html(self, header_text: str | None = None) -> str:
        mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        if header_text is None:
            return mailer.render(ProspectFactory(), "Hello", "<p>Body</p>").html
        return mailer.render(
            ProspectFactory(), "Hello", "<p>Body</p>", header_text=header_text
        ).html

    def test_the_header_text_replaces_the_site_name_at_the_top(self) -> None:
        html = self.render_html("Service desk")

        self.assertIn("Service desk", html.split("Body")[0])
        self.assertNotIn("Acme Club", html.split("Body")[0])

    def test_an_empty_header_text_falls_back_to_the_site_name(self) -> None:
        html = self.render_html("")

        self.assertIn("Acme Club", html.split("Body")[0])

    def test_no_header_text_falls_back_to_the_site_name(self) -> None:
        self.assertIn("Acme Club", self.render_html().split("Body")[0])

    def test_the_header_text_is_escaped(self) -> None:
        html = self.render_html("Q&A <b>live</b>")

        self.assertIn("Q&amp;A &lt;b&gt;live&lt;/b&gt;", html)
        self.assertNotIn("<b>live</b>", html)

    def test_the_header_text_is_not_run_through_variables(self) -> None:
        html = self.render_html("{{ first_name }}")

        self.assertIn("{{ first_name }}", html)
        self.assertNotIn("Ada", html.split("Body")[0])
