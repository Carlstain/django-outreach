from django.conf import settings
from django.test import Client, override_settings

from outreach.choices import ProspectStatus
from outreach.services.unsubscribe import SuppressionList, UnsubscribeTokens
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory
from tests.routes import outreach_help_url, outreach_unsubscribe_url

LOGIN_REQUIRED_MIDDLEWARE = [
    *settings.MIDDLEWARE,
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
]


@override_settings(MIDDLEWARE=LOGIN_REQUIRED_MIDDLEWARE, OUTREACH_LANGUAGE="en")
class UnsubscribeLoginRequiredTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.prospect = ProspectFactory()
        self.url = outreach_unsubscribe_url(UnsubscribeTokens().make(self.prospect))

    def test_the_middleware_is_active_for_other_pages(self) -> None:
        response = self.client.get(outreach_help_url())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/?next="))

    def test_anonymous_get_shows_the_confirmation_page(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.status, ProspectStatus.PROSPECT)

    def test_anonymous_post_unsubscribes(self) -> None:
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.status, ProspectStatus.UNSUBSCRIBED)
        self.assertTrue(SuppressionList().contains(self.prospect.email))
