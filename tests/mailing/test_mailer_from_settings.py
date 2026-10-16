from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from outreach.services.mailing import ProspectMailer
from tests.base import OutreachTestCase


class MailerFromSettingsTests(OutreachTestCase):
    @override_settings(OUTREACH_BASE_URL="https://outreach.example.test/")
    def test_the_mailer_uses_the_base_url_and_the_actor(self) -> None:
        mailer = ProspectMailer.from_settings("staff")

        self.assertEqual(mailer.base_url, "https://outreach.example.test")
        self.assertEqual(mailer.actor, "staff")

    def test_a_missing_or_empty_base_url_is_refused(self) -> None:
        for base_url in [None, ""]:
            with (
                self.subTest(base_url=base_url),
                override_settings(OUTREACH_BASE_URL=base_url),
                self.assertRaisesMessage(ImproperlyConfigured, "OUTREACH_BASE_URL is not set"),
            ):
                ProspectMailer.from_settings("staff")
