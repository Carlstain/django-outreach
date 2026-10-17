from django.test import override_settings

from outreach.services.unsubscribe import UnsubscribeTokens
from tests.base import OutreachTestCase, requires_translations
from tests.factories import ProspectFactory
from tests.routes import outreach_unsubscribe_url


@override_settings(OUTREACH_LANGUAGE="en")
class UnsubscribeLanguageTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        prospect = ProspectFactory()
        self.url = outreach_unsubscribe_url(UnsubscribeTokens().make(prospect))

    @requires_translations
    def test_the_page_follows_the_language_of_the_link(self) -> None:
        response = self.client.get(f"{self.url}?lang=pt-br")

        self.assertContains(response, "Deixar de receber e-mails de")

    @requires_translations
    def test_the_confirmation_keeps_the_language_of_the_link(self) -> None:
        response = self.client.post(f"{self.url}?lang=es")

        self.assertContains(response, "no recibirá más correos")

    @requires_translations
    def test_an_unknown_or_missing_language_uses_the_site_language(self) -> None:
        for query in ["", "?lang=", "?lang=xx", "?lang=<script>"]:
            with self.subTest(query=query):
                response = self.client.get(f"{self.url}{query}")

                self.assertNotContains(response, "baja")
                self.assertNotContains(response, "inscrição")

    @requires_translations
    @override_settings(OUTREACH_LANGUAGE="fr")
    def test_a_regional_code_falls_back_to_its_language(self) -> None:
        response = self.client.get(f"{self.url}?lang=es-MX")

        self.assertContains(response, "baja")
