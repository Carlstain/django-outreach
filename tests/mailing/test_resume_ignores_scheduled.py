from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from outreach.services.mailing import ProspectMailer
from outreach.services.scheduling import MailingScheduler
from outreach.tasks import deliver_mail
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery"
)
class ResumeIgnoresScheduledTests(OutreachTestCase):
    def test_a_scheduled_delivery_is_never_queued_by_the_resume_command(self) -> None:
        mailing = (
            MailingScheduler(ProspectMailer(MAIL_BASE_URL, "staff"))
            .schedule(
                [ProspectFactory()],
                "Subject",
                "<p>Body</p>",
                send_at=timezone.now() + timedelta(days=2),
            )
            .mailing
        )
        mailing.deliveries.update(updated_at=timezone.now() - timedelta(hours=5))
        output = StringIO()

        with (
            patch.object(deliver_mail, "apply_async") as apply_async,
            self.captureOnCommitCallbacks(execute=True),
        ):
            call_command("outreach_resume_deliveries", stdout=output)

        apply_async.assert_not_called()
        self.assertIn("Deliveries queued: 0.", output.getvalue())
