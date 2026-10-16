from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.services.mailing import ProspectMailer
from outreach.services.scheduling import MailingScheduler
from outreach.tasks import deliver_mail, send_due_mailings
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery"
)
class StartDueMailingsTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.scheduler = MailingScheduler(ProspectMailer(MAIL_BASE_URL, "staff"))
        self.now = timezone.now()
        self.due_mailing = self.schedule(self.now - timedelta(minutes=1))
        self.later_mailing = self.schedule(self.now + timedelta(hours=1))
        publisher = patch.object(deliver_mail, "apply_async")
        self.apply_async = publisher.start()
        self.addCleanup(publisher.stop)

    def schedule(self, send_at):
        return self.scheduler.schedule(
            [ProspectFactory()], "Subject", "<p>Body</p>", send_at=send_at
        ).mailing

    def statuses(self, mailing) -> set[str]:
        return set(mailing.deliveries.values_list("status", flat=True))

    def test_only_the_mailings_that_are_due_are_started(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            started_count = self.scheduler.start_due()

        self.assertEqual(started_count, 1)
        self.assertEqual(self.statuses(self.due_mailing), {DeliveryStatus.PENDING})
        self.assertEqual(self.statuses(self.later_mailing), {DeliveryStatus.SCHEDULED})
        self.assertEqual(self.apply_async.call_count, 1)

    def test_a_mailing_already_started_is_not_started_again(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self.scheduler.start_due()
            started_count = self.scheduler.start_due()

        self.assertEqual(started_count, 0)
        self.assertEqual(self.apply_async.call_count, 1)

    def test_the_celery_task_starts_the_due_mailings(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            started_count = send_due_mailings.apply().get()

        self.assertEqual(started_count, 1)
        self.assertEqual(self.statuses(self.due_mailing), {DeliveryStatus.PENDING})

    def test_the_command_starts_the_due_mailings_and_reports_the_count(self) -> None:
        output = StringIO()

        with self.captureOnCommitCallbacks(execute=True):
            call_command("outreach_send_due_mailings", stdout=output)

        self.assertIn("Mailings started: 1.", output.getvalue())
        self.assertEqual(self.statuses(self.due_mailing), {DeliveryStatus.PENDING})

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_the_command_refuses_sync_mode(self) -> None:
        with self.assertRaises(CommandError):
            call_command("outreach_send_due_mailings")
