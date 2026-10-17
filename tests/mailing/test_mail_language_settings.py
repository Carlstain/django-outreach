from django.core.checks import Error
from django.test import override_settings

from outreach.checks import check_mail_language
from outreach.conf import outreach_settings
from tests.base import OutreachTestCase


class MailLanguageSettingTests(OutreachTestCase):
    @override_settings(OUTREACH_LANGUAGE="fr")
    def test_the_mail_language_defaults_to_the_outreach_language(self) -> None:
        self.assertEqual(outreach_settings.mail_language, "fr")

    @override_settings(OUTREACH_LANGUAGE="en", OUTREACH_MAIL_LANGUAGE="pt_BR")
    def test_the_mail_language_can_differ_from_the_interface_language(self) -> None:
        self.assertEqual(outreach_settings.language, "en")
        self.assertEqual(outreach_settings.mail_language, "pt-br")

    @override_settings(OUTREACH_MAIL_LANGUAGE="de")
    def test_an_unshipped_mail_language_is_an_error(self) -> None:
        errors = check_mail_language(None)

        self.assertEqual([error.id for error in errors], ["outreach.E004"])
        self.assertIsInstance(errors[0], Error)

    @override_settings(OUTREACH_MAIL_LANGUAGE="pt-BR")
    def test_a_shipped_mail_language_passes_the_check(self) -> None:
        self.assertEqual(check_mail_language(None), [])

    def test_no_mail_language_passes_the_check(self) -> None:
        self.assertEqual(check_mail_language(None), [])
