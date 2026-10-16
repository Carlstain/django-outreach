from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import StateApps

from tests.base import OutreachTransactionTestCase

BEFORE = [("outreach", "0008_failure_kind")]
AFTER = [("outreach", "0009_scrub_failure_details")]


class FailureScrubMigrationTests(OutreachTransactionTestCase):
    def tearDown(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def apps_at(self, targets: list[tuple[str, str]]) -> StateApps:
        MigrationExecutor(connection).migrate(targets)
        return MigrationExecutor(connection).loader.project_state(targets).apps

    def test_old_failure_details_are_blanked_and_other_details_are_kept(self) -> None:
        old_apps = self.apps_at(BEFORE)
        prospect = old_apps.get_model("outreach", "Prospect").objects.create(
            email="someone@example.org"
        )
        event_model = old_apps.get_model("outreach", "ProspectEvent")
        event_model.objects.create(
            prospect=prospect, kind="mail_failed", detail="raw error for someone@example.org"
        )
        event_model.objects.create(prospect=prospect, kind="mailed", detail="A subject")

        new_apps = self.apps_at(AFTER)

        details = {
            event.kind: event.detail
            for event in new_apps.get_model("outreach", "ProspectEvent").objects.all()
        }
        self.assertEqual(details, {"mail_failed": "", "mailed": "A subject"})
