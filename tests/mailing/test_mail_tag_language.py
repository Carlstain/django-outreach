from django.test import override_settings
from django.utils import translation

from tests.base import OutreachMailTagTestCase, requires_translations
from tests.factories import ProspectFactory


@override_settings(OUTREACH_LANGUAGE="fr", TIME_ZONE="UTC")
class MailTagLanguageTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospect = ProspectFactory()

    @requires_translations
    def test_the_greeting_is_translated_to_the_outreach_language(self) -> None:
        for hour, expected in {9: "Bonjour", 14: "Bon après-midi", 20: "Bonsoir"}.items():
            with self.subTest(hour=hour), self.freeze_time(hour=hour):
                rendered = self.render_mail(self.prospect, subject="{% greeting %}")

                self.assertEqual(rendered.subject, expected)

    @requires_translations
    def test_the_date_is_formatted_in_the_outreach_language(self) -> None:
        with self.freeze_time(hour=9):
            rendered = self.render_mail(self.prospect, subject='{% today "j F Y" %}')

        self.assertEqual(rendered.subject, "14 mai 2026")

    def test_the_active_language_is_restored_after_rendering(self) -> None:
        with translation.override("en"):
            self.render_mail(self.prospect, subject="{% greeting %}")

            self.assertEqual(translation.get_language(), "en")
