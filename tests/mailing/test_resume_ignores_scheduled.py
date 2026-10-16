from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory


class ResumeIgnoresScheduledTests(CeleryMailTestCase):
    def test_a_scheduled_delivery_is_never_queued_by_the_resume_command(self) -> None:
        mailing = self.scheduler.schedule(
            [ProspectFactory()],
            "Subject",
            "<p>Body</p>",
            send_at=timezone.now() + timedelta(days=2),
        ).mailing
        mailing.deliveries.update(updated_at=timezone.now() - timedelta(hours=5))
        output = StringIO()

        with self.captureOnCommitCallbacks(execute=True):
            call_command("outreach_resume_deliveries", stdout=output)

        self.apply_async.assert_not_called()
        self.assertIn("Deliveries queued: 0.", output.getvalue())
