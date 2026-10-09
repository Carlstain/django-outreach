from django.test import override_settings

from tests.base import OutreachTestCase
from tests.factories import create_outreach_staff_user
from tests.routes import (
    django_admin_index_url,
    outreach_help_url,
    outreach_index_url,
    outreach_login_url,
)

LINK_TEXT = "Open Django admin"


@override_settings(OUTREACH_LANGUAGE="en")
class AdminLinkTests(OutreachTestCase):
    def test_link_to_the_django_admin_is_shown_when_it_is_mounted(self) -> None:
        self.client.force_login(create_outreach_staff_user())

        for page_url in (outreach_index_url(), outreach_help_url()):
            with self.subTest(page_url=page_url):
                response = self.client.get(page_url)

                self.assertContains(
                    response,
                    f'<a class="linkout" href="{django_admin_index_url()}">{LINK_TEXT}',
                )

    @override_settings(ROOT_URLCONF="tests.urls.no_admin")
    def test_pages_render_without_the_django_admin_and_have_no_link(self) -> None:
        self.client.force_login(create_outreach_staff_user())

        for page_url in (outreach_index_url(), outreach_help_url()):
            with self.subTest(page_url=page_url):
                response = self.client.get(page_url)

                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, LINK_TEXT)
                self.assertNotContains(response, 'class="linkout"')

    @override_settings(ROOT_URLCONF="tests.urls.no_admin")
    def test_login_page_renders_without_the_django_admin(self) -> None:
        response = self.client.get(outreach_login_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, LINK_TEXT)
