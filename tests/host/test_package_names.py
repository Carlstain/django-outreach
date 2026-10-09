from django.apps import apps
from django.contrib.staticfiles import finders
from django.template.loader import get_template
from django.urls import reverse

from outreach.conf import outreach_settings
from outreach.sites import outreach_site
from tests.base import OutreachTestCase

EXPECTED_TABLES = {
    "outreach_prospect",
    "outreach_prospectevent",
    "outreach_mailing",
    "outreach_suppression",
    "outreach_emailtemplate",
}


class PackageNamesTests(OutreachTestCase):
    def test_app_label_and_site_name_use_the_package_name(self) -> None:
        app_config = apps.get_app_config("outreach")

        self.assertEqual((app_config.name, app_config.label), ("outreach", "outreach"))
        self.assertEqual(outreach_site.name, "outreach_admin")

    def test_every_table_starts_with_the_package_name(self) -> None:
        tables = {
            model._meta.db_table for model in apps.get_app_config("outreach").get_models()
        }

        self.assertEqual(tables, EXPECTED_TABLES)

    def test_url_namespaces_use_the_package_name(self) -> None:
        self.assertEqual(
            reverse("outreach:unsubscribe", args=["token"]), "/outreach/unsubscribe/token/"
        )
        self.assertEqual(reverse("outreach_admin:index"), "/outreach/")

    def test_templates_and_static_files_live_under_the_package_name(self) -> None:
        get_template("outreach/base.html")
        self.assertIsNotNone(finders.find("outreach/outreach.css"))

    def test_settings_are_read_from_the_package_prefixed_names(self) -> None:
        self.assertEqual(outreach_settings.base_url, "https://testserver")
        self.assertEqual(outreach_settings.site_name, "Outreach")
