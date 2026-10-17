from django.test import override_settings

from tests.base import OutreachTestCase, requires_translations
from tests.factories import create_outreach_staff_user
from tests.routes import outreach_index_url, outreach_login_url, outreach_set_language_url


@override_settings(OUTREACH_LANGUAGE="en")
class AdminLanguageTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

    @requires_translations
    def test_the_cookie_switches_the_interface_language(self) -> None:
        self.client.cookies["outreach_language"] = "es"

        response = self.client.get(outreach_index_url())

        self.assertContains(response, "Cerrar sesión")

    @requires_translations
    def test_a_regional_cookie_value_selects_the_regional_catalogue(self) -> None:
        self.client.cookies["outreach_language"] = "pt_BR"

        response = self.client.get(outreach_index_url())

        self.assertContains(response, "Encerrar sessão")

    @requires_translations
    def test_an_invalid_cookie_falls_back_to_the_site_language(self) -> None:
        self.client.cookies["outreach_language"] = "klingon"

        response = self.client.get(outreach_index_url())

        self.assertContains(response, "Log out")

    @requires_translations
    def test_the_login_page_follows_the_cookie_too(self) -> None:
        self.client.logout()
        self.client.cookies["outreach_language"] = "fr"

        response = self.client.get(outreach_login_url())

        self.assertContains(response, "Connexion à Outreach")

    def test_the_menu_lists_every_shipped_language(self) -> None:
        response = self.client.get(outreach_index_url())

        for label in ["English", "Français", "Español", "Português", "Português (Brasil)"]:
            self.assertContains(response, f">{label}</option>")


@override_settings(OUTREACH_LANGUAGE="en")
class SetLanguageViewTests(OutreachTestCase):
    def test_a_valid_choice_sets_the_cookie_and_redirects_back(self) -> None:
        response = self.client.post(
            outreach_set_language_url(), {"language": "pt-br", "next": outreach_index_url()}
        )

        self.assertRedirects(response, outreach_index_url(), fetch_redirect_response=False)
        cookie = response.cookies["outreach_language"]
        self.assertEqual(cookie.value, "pt-br")
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_an_unknown_language_sets_no_cookie(self) -> None:
        response = self.client.post(outreach_set_language_url(), {"language": "klingon"})

        self.assertNotIn("outreach_language", response.cookies)

    def test_an_unsafe_next_address_is_replaced_by_the_dashboard(self) -> None:
        response = self.client.post(
            outreach_set_language_url(),
            {"language": "es", "next": "https://evil.example.org/"},
        )

        self.assertRedirects(response, outreach_index_url(), fetch_redirect_response=False)

    def test_only_post_is_allowed(self) -> None:
        response = self.client.get(outreach_set_language_url())

        self.assertEqual(response.status_code, 405)

    def test_an_anonymous_visitor_can_choose_a_language(self) -> None:
        response = self.client.post(outreach_set_language_url(), {"language": "fr"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies["outreach_language"].value, "fr")
