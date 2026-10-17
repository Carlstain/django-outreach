from django.core import mail
from django.test import override_settings

from outreach.models import Mailing
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachMailTagTestCase, requires_translations
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", TIME_ZONE="UTC")
class MailLanguageTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.prospect = ProspectFactory(first_name="Ada")

    @requires_translations
    def test_the_greeting_follows_the_language_of_the_mail_and_the_body_is_untouched(
        self,
    ) -> None:
        with self.freeze_time(hour=9):
            rendered = self.mailer.render(
                self.prospect,
                "{% greeting %}",
                "<p>Good morning {{ first_name }}</p>",
                language="es",
            )

        self.assertEqual(rendered.subject, "Buenos días")
        self.assertIn("Good morning Ada", rendered.html)

    @requires_translations
    def test_the_footer_is_translated_for_each_shipped_language(self) -> None:
        expected_by_language = {
            "fr": "Se désinscrire",
            "es": "Darse de baja",
            "pt": "Cancelar a subscrição",
            "pt-br": "Cancelar a inscrição",
        }
        for language, expected in expected_by_language.items():
            with self.subTest(language=language):
                rendered = self.mailer.render(
                    self.prospect, "Subject", "<p>Body</p>", language=language
                )

                self.assertIn(expected, rendered.html)

    def test_the_unsubscribe_link_names_the_language_only_when_it_differs_from_the_site(
        self,
    ) -> None:
        spanish = self.mailer.render(self.prospect, "Subject", "<p>Body</p>", language="es")
        english = self.mailer.render(self.prospect, "Subject", "<p>Body</p>", language="en")
        unspecified = self.mailer.render(self.prospect, "Subject", "<p>Body</p>")

        self.assertIn("?lang=es", spanish.html)
        self.assertNotIn("?lang=", english.html)
        self.assertNotIn("?lang=", unspecified.html)

    def test_a_send_stores_the_language_and_marks_the_unsubscribe_header(self) -> None:
        self.mailer.send([self.prospect], "Subject", "<p>Body</p>", language="pt-br")

        mailing = Mailing.objects.get()
        self.assertEqual(mailing.language, "pt-br")
        self.assertIn("?lang=pt-br", mail.outbox[0].extra_headers["List-Unsubscribe"])

    @override_settings(OUTREACH_MAIL_LANGUAGE="fr")
    def test_a_send_without_a_language_stores_the_mail_default(self) -> None:
        self.mailer.send([self.prospect], "Subject", "<p>Body</p>")

        self.assertEqual(Mailing.objects.get().language, "fr")

    @requires_translations
    def test_an_old_mailing_with_no_language_is_sent_in_the_site_language(self) -> None:
        self.mailer.send([self.prospect], "Subject", "<p>Body</p>", language="es")
        Mailing.objects.update(language="")
        self.prospect.refresh_from_db()

        rendered = self.mailer.render(self.prospect, "Subject", "<p>Body</p>", language="")

        self.assertIn("Unsubscribe", rendered.html)
        self.assertNotIn("?lang=", rendered.html)

    @requires_translations
    def test_a_test_send_uses_the_language_of_the_mail(self) -> None:
        self.mailer.send_sample(
            self.prospect, "Subject", "<p>Body</p>", "staff@example.org", language="es"
        )

        self.assertIn("Darse de baja", mail.outbox[0].alternatives[0][0])
