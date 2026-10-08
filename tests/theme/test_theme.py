import re

from django.core import mail
from django.core.checks import run_checks
from django.test import override_settings

from outreach.choices import EventKind
from outreach.models import ProspectEvent
from outreach.services.mailing import ProspectMailer
from outreach.services.unsubscribe import UnsubscribeTokens
from outreach.theme import OutreachTheme, warned_problems
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory
from tests.routes import outreach_login_url, outreach_unsubscribe_url

DEFAULT_LIGHT = {
    "brand": "#1f2a44",
    "accent": "#2563eb",
    "on_accent": "#ffffff",
    "text": "#1f2937",
    "muted": "#6b7280",
    "background": "#f8fafc",
    "surface": "#ffffff",
    "border": "#e5e7eb",
}
DEFAULT_DARK = {
    "brand": "#93a4c6",
    "accent": "#60a5fa",
    "on_accent": "#0b1220",
    "text": "#e5e7eb",
    "muted": "#9ca3af",
    "background": "#0b1220",
    "surface": "#111a2e",
    "border": "#243049",
}
SYSTEM_FONT_STACK = (
    "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
)
DEFAULT_CSS = (
    ":root{color-scheme:light dark;"
    "--brand:#1f2a44;--accent:#2563eb;--on-accent:#ffffff;--fg:#1f2937;--muted:#6b7280;"
    "--bg:#f8fafc;--surface:#ffffff;--line:#e5e7eb;"
    f"--font-ui:{SYSTEM_FONT_STACK};}}"
    "@media (prefers-color-scheme: dark){:root{"
    "--brand:#93a4c6;--accent:#60a5fa;--on-accent:#0b1220;--fg:#e5e7eb;--muted:#9ca3af;"
    "--bg:#0b1220;--surface:#111a2e;--line:#243049;}}"
)
DISTINCT_THEME = {
    "brand": "#0a0b0c",
    "accent": "#0d0e0f",
    "on_accent": "#101112",
    "text": "#131415",
    "muted": "#161718",
    "background": "#191a1b",
    "surface": "#1c1d1e",
    "border": "#1f2021",
}
HEX_COLOR_PATTERN = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def theme_errors() -> list[str]:
    return [message.msg for message in run_checks() if message.id == "outreach.E001"]


class ThemeTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        warned_problems.clear()

    def assert_falls_back(self, theme: object, expected_message: str) -> None:
        warned_problems.clear()
        with override_settings(OUTREACH_THEME=theme):
            self.assertEqual(theme_errors(), [expected_message])
            with self.assertLogs("outreach", level="WARNING") as captured:
                css = OutreachTheme().css()
            self.assertEqual(css, DEFAULT_CSS)
            self.assertEqual(
                [record.getMessage() for record in captured.records],
                [f"{expected_message} The default is used instead."],
            )

    def test_defaults_are_the_neutral_palette(self) -> None:
        theme = OutreachTheme()

        self.assertEqual(theme.light(), DEFAULT_LIGHT)
        self.assertEqual(theme.dark(), DEFAULT_DARK)
        self.assertEqual(theme.font_family(), SYSTEM_FONT_STACK)
        self.assertEqual(theme_errors(), [])

    def test_default_css_is_exactly_the_neutral_palette(self) -> None:
        self.assertEqual(OutreachTheme().css(), DEFAULT_CSS)

    @override_settings(OUTREACH_THEME={"brand": "#112233", "accent": "rebeccapurple"})
    def test_partial_override_merges_with_the_defaults(self) -> None:
        self.assertEqual(
            OutreachTheme().light(),
            {**DEFAULT_LIGHT, "brand": "#112233", "accent": "rebeccapurple"},
        )
        self.assertEqual(OutreachTheme().dark(), DEFAULT_DARK)

    @override_settings(OUTREACH_THEME=DISTINCT_THEME)
    def test_full_override_replaces_every_light_colour(self) -> None:
        self.assertEqual(OutreachTheme().light(), DISTINCT_THEME)

    @override_settings(OUTREACH_THEME={"dark": {"background": "#000000", "text": "#fafafa"}})
    def test_dark_block_overrides_only_the_given_keys(self) -> None:
        self.assertEqual(
            OutreachTheme().dark(),
            {**DEFAULT_DARK, "background": "#000000", "text": "#fafafa"},
        )
        self.assertEqual(OutreachTheme().light(), DEFAULT_LIGHT)

    @override_settings(OUTREACH_THEME={"font_family": "Verdana, 'Trebuchet MS', sans-serif"})
    def test_font_family_is_used_when_given(self) -> None:
        self.assertEqual(OutreachTheme().font_family(), "Verdana, 'Trebuchet MS', sans-serif")
        self.assertIn("--font-ui:Verdana, 'Trebuchet MS', sans-serif;", OutreachTheme().css())

    @override_settings(OUTREACH_THEME={"avatar": "#abcdef", "brand": "#112233"})
    def test_css_declares_the_avatar_and_overridden_variables(self) -> None:
        light_block = OutreachTheme().css().split("@media")[0]

        self.assertIn("--brand:#112233;", light_block)
        self.assertIn("--avatar-bg:#abcdef;", light_block)
        self.assertIn("--accent:#2563eb;", light_block)

    @override_settings(
        OUTREACH_THEME={"brand": "#112233", "font_family": "Verdana, sans-serif"}
    )
    def test_public_pages_embed_the_theme_style_block(self) -> None:
        prospect = ProspectFactory()
        unsubscribe_page = self.client.get(
            outreach_unsubscribe_url(UnsubscribeTokens().make(prospect))
        )
        login_page = self.client.get(outreach_login_url())

        expected_block = f"<style>{OutreachTheme().css()}</style>"
        self.assertContains(unsubscribe_page, expected_block, html=False)
        self.assertContains(login_page, expected_block, html=False)

    @override_settings(OUTREACH_THEME=DISTINCT_THEME)
    def test_email_html_uses_only_the_theme_colours(self) -> None:
        prospect = ProspectFactory()
        mailer = ProspectMailer("https://outreach.example.test", "tester")

        rendered = mailer.render(
            prospect, "Hi", "<h1>Title</h1><blockquote>q</blockquote><p>b</p>"
        )

        found_colours = set(HEX_COLOR_PATTERN.findall(rendered.html))
        self.assertTrue(found_colours)
        self.assertLessEqual(found_colours, set(DISTINCT_THEME.values()))
        self.assertIn("background-color: #191a1b", rendered.html)
        self.assertIn("color: #0a0b0c", rendered.html)

    def test_email_html_uses_the_neutral_palette_by_default(self) -> None:
        prospect = ProspectFactory()
        mailer = ProspectMailer("https://outreach.example.test", "tester")

        rendered = mailer.render(prospect, "Hi", "<p>Body</p>")

        found_colours = set(HEX_COLOR_PATTERN.findall(rendered.html))
        self.assertTrue(found_colours)
        self.assertLessEqual(found_colours, set(DEFAULT_LIGHT.values()))

    def test_invalid_colours_are_reported_by_the_check_and_fall_back_in_css(self) -> None:
        invalid_values = [
            "red; } body { display:none",
            "</style>",
            "url(https://evil.test/x.png)",
            "#12",
            "not a colour",
            "red !important",
            123,
        ]

        for invalid_value in invalid_values:
            with self.subTest(value=invalid_value):
                self.assert_falls_back(
                    {"accent": invalid_value},
                    "OUTREACH_THEME['accent'] is not a valid CSS color.",
                )

    def test_css_injection_through_the_dark_block_falls_back(self) -> None:
        injected = {"dark": {"surface": "red; } body { display:none"}}

        self.assert_falls_back(
            injected, "OUTREACH_THEME['dark']['surface'] is not a valid CSS color."
        )

    def test_invalid_font_families_are_reported_and_fall_back(self) -> None:
        invalid_values = ["Arial; } body { display:none", "</style>", "Arial{}", ""]

        for invalid_value in invalid_values:
            with self.subTest(value=invalid_value):
                self.assert_falls_back(
                    {"font_family": invalid_value},
                    "OUTREACH_THEME['font_family'] is not a valid font stack.",
                )

    def test_unknown_key_is_reported_and_ignored(self) -> None:
        self.assert_falls_back(
            {"colour": "red"}, "OUTREACH_THEME has an unknown key: 'colour'."
        )

    @override_settings(OUTREACH_THEME={"dark": {"font_family": "Arial"}})
    def test_unknown_key_in_the_dark_block_is_reported(self) -> None:
        self.assertEqual(
            theme_errors(), ["OUTREACH_THEME['dark'] has an unknown key: 'font_family'."]
        )

    def test_non_dict_theme_is_reported_and_falls_back(self) -> None:
        self.assert_falls_back("red", "OUTREACH_THEME must be a dict.")

    def test_non_dict_dark_block_is_reported_and_falls_back(self) -> None:
        self.assert_falls_back({"dark": "red"}, "OUTREACH_THEME['dark'] must be a dict.")

    def test_valid_colour_notations_are_accepted(self) -> None:
        accepted = {
            "brand": "#abc",
            "accent": "rgb(10, 20, 30)",
            "muted": "hsl(120 50% 50%)",
            "text": "rgba(0,0,0,0.5)",
            "border": "rebeccapurple",
        }

        with override_settings(OUTREACH_THEME=accepted):
            self.assertEqual(theme_errors(), [])
            self.assertEqual(OutreachTheme().light(), {**DEFAULT_LIGHT, **accepted})

    def test_hex_colours_accept_3_4_6_and_8_digits_only(self) -> None:
        for accepted in ("#abc", "#abcd", "#abcdef", "#abcdef12", "#ABCDEF"):
            with (
                self.subTest(accepted=accepted),
                override_settings(OUTREACH_THEME={"accent": accepted}),
            ):
                self.assertEqual(theme_errors(), [])
        for rejected in ("#ab", "#abcde", "#abcdef1", "#abcdef123"):
            with self.subTest(rejected=rejected):
                self.assert_check_rejects_accent(rejected)

    def test_colour_functions_accept_modern_syntax(self) -> None:
        for accepted in ("RGB(0,0,0)", "hsl(120deg 50% 50%)", "rgb(0 0 0 / 50%)"):
            with (
                self.subTest(accepted=accepted),
                override_settings(OUTREACH_THEME={"accent": accepted}),
            ):
                self.assertEqual(theme_errors(), [])
                self.assertEqual(OutreachTheme().light()["accent"], accepted)

    def test_malformed_colour_functions_and_overlong_values_are_rejected(self) -> None:
        for rejected in (
            "rgb(a)",
            "rgb(url)",
            "rgb(0,0)",
            "a" * 101,
            "rgb(" + "0," * 60 + "0)",
        ):
            with self.subTest(rejected=rejected):
                self.assert_check_rejects_accent(rejected)

    def test_font_families_accept_quoted_and_plain_names(self) -> None:
        for accepted in ('"Inter", sans-serif', "Open Sans", "'Segoe UI', Arial"):
            with (
                self.subTest(accepted=accepted),
                override_settings(OUTREACH_THEME={"font_family": accepted}),
            ):
                self.assertEqual(theme_errors(), [])
                self.assertEqual(OutreachTheme().font_family(), accepted)

    def test_font_families_reject_unbalanced_quotes_separators_and_long_values(self) -> None:
        for rejected in (
            "a'b",
            "'unclosed",
            "a;b",
            "a" * 201,
            " ",
            "-",
            "--x",
            '""',
            "''",
            "1abc",
            "_hidden",
            "Arial, -",
        ):
            with (
                self.subTest(rejected=rejected),
                override_settings(OUTREACH_THEME={"font_family": rejected}),
            ):
                self.assertEqual(
                    theme_errors(),
                    ["OUTREACH_THEME['font_family'] is not a valid font stack."],
                )

    def test_each_distinct_problem_is_logged_once(self) -> None:
        theme = {"accent": "#12", "muted": "nope nope", "dark": {"brand": "#12"}}

        with override_settings(OUTREACH_THEME=theme), self.assertLogs("outreach") as captured:
            OutreachTheme().css()
            OutreachTheme().css()
            email_accent = OutreachTheme().email.accent

        self.assertEqual(email_accent, DEFAULT_LIGHT["accent"])
        self.assertEqual(
            sorted(record.getMessage() for record in captured.records),
            [
                "OUTREACH_THEME['accent'] is not a valid CSS color. The default is used instead.",
                "OUTREACH_THEME['dark']['brand'] is not a valid CSS color. "
                "The default is used instead.",
                "OUTREACH_THEME['muted'] is not a valid CSS color. The default is used instead.",
            ],
        )

    def test_an_invalid_key_falls_back_while_valid_keys_still_apply(self) -> None:
        theme = {
            "brand": "#112233",
            "accent": "#12",
            "dark": {"text": "#fafafa", "border": "x"},
        }

        with override_settings(OUTREACH_THEME=theme), self.assertLogs("outreach"):
            light = OutreachTheme().light()
            dark = OutreachTheme().dark()

        self.assertEqual(light, {**DEFAULT_LIGHT, "brand": "#112233"})
        self.assertEqual(dark, {**DEFAULT_DARK, "text": "#fafafa"})

    @override_settings(
        OUTREACH_THEME={"accent": "#12"}, OUTREACH_BASE_URL="https://outreach.example.test"
    )
    def test_invalid_theme_never_breaks_public_pages_or_sending(self) -> None:
        prospect = ProspectFactory()
        mailer = ProspectMailer("https://outreach.example.test", "tester")

        with self.assertLogs("outreach", level="WARNING"):
            page = self.client.get(
                outreach_unsubscribe_url(UnsubscribeTokens().make(prospect))
            )
            report = mailer.send([prospect], "Hi", "<p>Body</p>")

        self.assertContains(page, f"<style>{DEFAULT_CSS}</style>")
        self.assertEqual(report.sent, [prospect])
        self.assertEqual(report.failed, [])
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(ProspectEvent.objects.filter(kind=EventKind.MAIL_FAILED).exists())
        self.assertEqual(
            theme_errors(), ["OUTREACH_THEME['accent'] is not a valid CSS color."]
        )

    def assert_check_rejects_accent(self, rejected: object) -> None:
        with override_settings(OUTREACH_THEME={"accent": rejected}):
            self.assertEqual(
                theme_errors(), ["OUTREACH_THEME['accent'] is not a valid CSS color."]
            )

    def test_degenerate_font_families_fall_back_to_the_system_stack(self) -> None:
        for degenerate in (" ", "-", "--x", '""'):
            with self.subTest(font_family=degenerate):
                self.assert_falls_back(
                    {"font_family": degenerate},
                    "OUTREACH_THEME['font_family'] is not a valid font stack.",
                )
