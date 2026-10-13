from django.test import override_settings

from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory

LOGO_SETTINGS = {
    "OUTREACH_BASE_URL": MAIL_BASE_URL,
    "OUTREACH_LANGUAGE": "en",
    "OUTREACH_LOGO_STATIC_PATH": "brand/logo.png",
}


class MailLogoTests(OutreachTestCase):
    def render_html(self, *, is_newsletter: bool = True) -> str:
        return (
            ProspectMailer(MAIL_BASE_URL, "staff")
            .render(ProspectFactory(), "Hello", "<p>Body</p>", is_newsletter=is_newsletter)
            .html
        )

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
