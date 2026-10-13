from django.test import override_settings

from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory

LOGO_SETTINGS = {
    "OUTREACH_BASE_URL": MAIL_BASE_URL,
    "OUTREACH_LANGUAGE": "en",
    "OUTREACH_LOGO_STATIC_PATH": "brand/logo.png",
    "OUTREACH_SITE_NAME": "Acme Club",
}
CENTERED_HEADER_CELL = 'align="center" style="padding: 24px 32px 0 32px'


class MailLogoTests(OutreachTestCase):
    def render_html(self, *, is_newsletter: bool = True, header_text: str = "") -> str:
        return (
            ProspectMailer(MAIL_BASE_URL, "staff")
            .render(
                ProspectFactory(),
                "Hello",
                "<p>Body</p>",
                header_text=header_text,
                is_newsletter=is_newsletter,
            )
            .html
        )

    def header_part(self, html: str) -> str:
        return html.split("Body")[0]

    @override_settings(**LOGO_SETTINGS)
    def test_there_is_no_logo_by_default(self) -> None:
        self.assertNotIn("<img", self.render_html())

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True)
    def test_the_header_logo_comes_before_the_body(self) -> None:
        html = self.render_html()

        self.assertEqual(html.count("<img"), 1)
        self.assertLess(html.index("<img"), html.index("Body"))

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_FOOTER=True)
    def test_the_footer_logo_comes_after_the_body(self) -> None:
        html = self.render_html()

        self.assertEqual(html.count("<img"), 1)
        self.assertGreater(html.index("<img"), html.index("Body"))

    @override_settings(
        **LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True, OUTREACH_EMAIL_LOGO_IN_FOOTER=True
    )
    def test_the_logo_can_be_in_the_header_and_the_footer(self) -> None:
        self.assertEqual(self.render_html().count("<img"), 2)

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True)
    def test_the_logo_address_is_absolute_and_built_from_the_base_url(self) -> None:
        self.assertIn(f'src="{MAIL_BASE_URL}/static/brand/logo.png"', self.render_html())

    @override_settings(
        OUTREACH_BASE_URL=MAIL_BASE_URL,
        OUTREACH_EMAIL_LOGO_IN_HEADER=True,
        OUTREACH_EMAIL_LOGO_IN_FOOTER=True,
    )
    def test_no_logo_path_means_no_image_even_when_placed(self) -> None:
        self.assertNotIn("<img", self.render_html())

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_FOOTER=True)
    def test_a_notice_keeps_the_footer_logo_without_the_unsubscribe_line(self) -> None:
        html = self.render_html(is_newsletter=False)

        self.assertEqual(html.count("<img"), 1)
        self.assertNotIn("Unsubscribe", html)

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True)
    def test_a_notice_without_a_footer_logo_has_no_footer(self) -> None:
        html = self.render_html(is_newsletter=False)

        self.assertEqual(html.count("border-top"), 0)

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True)
    def test_the_header_logo_alone_replaces_the_site_name_text(self) -> None:
        header = self.header_part(self.render_html())

        self.assertIn('alt="Acme Club"', header)
        self.assertNotIn("Acme Club", header.replace('alt="Acme Club"', ""))

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True)
    def test_the_header_logo_and_a_header_text_are_both_rendered(self) -> None:
        header = self.header_part(self.render_html(header_text="Service desk"))

        self.assertIn("<img", header)
        self.assertIn('alt="Service desk"', header)
        self.assertIn("Service desk", header.replace('alt="Service desk"', ""))
        self.assertNotIn("Acme Club", header)

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_FOOTER=True)
    def test_without_a_header_logo_the_site_name_is_still_the_header_text(self) -> None:
        header = self.header_part(self.render_html())

        self.assertIn("Acme Club", header)
        self.assertNotIn("<img", header)

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True)
    def test_the_header_logo_is_centered(self) -> None:
        html = self.render_html()

        self.assertIn(CENTERED_HEADER_CELL, html)
        self.assertIn("margin: 0 auto;", html)

    @override_settings(**LOGO_SETTINGS, OUTREACH_EMAIL_LOGO_IN_HEADER=True)
    def test_a_header_text_under_the_logo_is_centered_with_it(self) -> None:
        html = self.render_html(header_text="Service desk")

        self.assertIn(CENTERED_HEADER_CELL, html)
        self.assertIn("text-align: center;", self.header_part(html))
        self.assertIn("margin: 0 auto 8px auto;", html)

    @override_settings(**LOGO_SETTINGS)
    def test_the_header_is_not_centered_without_a_header_logo(self) -> None:
        html = self.render_html()

        self.assertNotIn(CENTERED_HEADER_CELL, html)
        self.assertNotIn("text-align: center;", self.header_part(html))
