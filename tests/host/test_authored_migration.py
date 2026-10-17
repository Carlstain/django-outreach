from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import StateApps

from tests.base import OutreachTransactionTestCase

BEFORE = [("outreach", "0003_mailingdelivery")]
AFTER = [("outreach", "0004_authored_email_templates")]
AUTHOR_USERNAME = "author@example.test"


class AuthoredMigrationTests(OutreachTransactionTestCase):
    def tearDown(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def apps_at(self, targets: list[tuple[str, str]]) -> StateApps:
        MigrationExecutor(connection).migrate(targets)
        return MigrationExecutor(connection).loader.project_state(targets).apps

    def create_old_author(self, old_apps: StateApps) -> object:
        user_model = old_apps.get_model(settings.AUTH_USER_MODEL)
        return user_model.objects.create(**{get_user_model().USERNAME_FIELD: AUTHOR_USERNAME})

    def create_old_template(self, old_apps: StateApps, name: str, created_by: str) -> None:
        old_apps.get_model("outreach", "EmailTemplate").objects.create(
            name=name, subject="Subject", body_html="<p>Body</p>", created_by=created_by
        )

    def test_existing_authors_are_matched_to_users_and_unknown_ones_are_cleared(self) -> None:
        old_apps = self.apps_at(BEFORE)
        author = self.create_old_author(old_apps)
        for name, created_by in [
            ("Known", AUTHOR_USERNAME),
            ("Also known", AUTHOR_USERNAME),
            ("Departed", "ghost@example.test"),
            ("Anonymous", ""),
        ]:
            self.create_old_template(old_apps, name, created_by)

        new_apps = self.apps_at(AFTER)

        authors_by_name = {
            template.name: template.created_by_id
            for template in new_apps.get_model("outreach", "EmailTemplate").objects.all()
        }
        self.assertEqual(
            authors_by_name,
            {"Known": author.pk, "Also known": author.pk, "Departed": None, "Anonymous": None},
        )

    def test_migrating_back_restores_the_author_names(self) -> None:
        old_apps = self.apps_at(BEFORE)
        self.create_old_author(old_apps)
        self.create_old_template(old_apps, "Known", AUTHOR_USERNAME)
        self.apps_at(AFTER)

        restored_apps = self.apps_at(BEFORE)

        restored = restored_apps.get_model("outreach", "EmailTemplate").objects.get()
        self.assertEqual(restored.created_by, AUTHOR_USERNAME)
