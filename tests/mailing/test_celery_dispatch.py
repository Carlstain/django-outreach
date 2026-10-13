from unittest.mock import patch

from django.core import mail
from django.test import override_settings

from outreach.services.mailing import ProspectMailer
from outreach.tasks import deliver_mail
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery"
)
class CeleryDispatchTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.prospects = [ProspectFactory(), ProspectFactory()]
        publisher = patch.object(deliver_mail, "apply_async")
        self.apply_async = publisher.start()
        self.addCleanup(publisher.stop)

    def test_one_task_is_published_per_delivery_after_the_commit(self) -> None:
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            report = self.mailer.send(self.prospects, "Subject", "<p>Body</p>")

        self.assertEqual(len(callbacks), 2)
        self.apply_async.assert_not_called()
        for callback in callbacks:
            callback()
        published_pks = sorted(call.kwargs["args"][0] for call in self.apply_async.mock_calls)
        self.assertEqual(
            published_pks,
            sorted(str(pk) for pk in report.mailing.deliveries.values_list("pk", flat=True)),
        )

    def test_the_report_lists_the_queued_prospects_and_nothing_is_sent(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            report = self.mailer.send(self.prospects, "Subject", "<p>Body</p>")

        self.assertEqual(report.queued, self.prospects)
        self.assertEqual(report.sent, [])
        self.assertEqual(report.failed, [])
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(OUTREACH_CELERY_QUEUE="outreach")
    def test_the_tasks_go_to_the_configured_queue(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self.mailer.send(self.prospects, "Subject", "<p>Body</p>")

        queues = {call.kwargs["queue"] for call in self.apply_async.mock_calls}
        self.assertEqual(queues, {"outreach"})

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_sync_mode_sends_inside_the_call_and_publishes_nothing(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            report = self.mailer.send(self.prospects, "Subject", "<p>Body</p>")

        self.assertEqual(report.sent, self.prospects)
        self.assertEqual(report.queued, [])
        self.assertEqual(len(mail.outbox), 2)
        self.apply_async.assert_not_called()
