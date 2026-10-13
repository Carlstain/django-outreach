import threading
from unittest import skipUnless
from unittest.mock import patch

from django.core import mail
from django.db import connection, connections
from django.test import override_settings

from outreach.models import Mailing
from outreach.services.mailing import MailReport, ProspectMailer
from tests.base import OutreachTransactionTestCase
from tests.factories import ProspectFactory

BASE_URL = "https://outreach.example.test"
WAIT_SECONDS = 20


@skipUnless(
    connection.vendor == "postgresql",
    "row locks with skip_locked need PostgreSQL, SQLite serialises writers instead",
)
@override_settings(OUTREACH_BASE_URL=BASE_URL, OUTREACH_LANGUAGE="en")
class SendMailConcurrencyTests(OutreachTransactionTestCase):
    def test_overlapping_sends_never_mail_the_same_recipient_twice(self) -> None:
        prospects = [ProspectFactory() for _ in range(5)]
        first_has_claimed = threading.Event()
        second_has_finished = threading.Event()
        reports: dict[str, MailReport] = {}
        original_plan = ProspectMailer.plan

        def plan_then_hold_the_locks(
            mailer: ProspectMailer, selected: list, **options: bool
        ) -> object:
            plan = original_plan(mailer, selected, **options)
            if mailer.actor == "first":
                first_has_claimed.set()
                second_has_finished.wait(WAIT_SECONDS)
            return plan

        def run_send(actor: str) -> None:
            try:
                mailer = ProspectMailer(BASE_URL, actor)
                reports[actor] = mailer.send(prospects, "Subject", "<p>Body</p>")
            finally:
                connections.close_all()

        first_thread = threading.Thread(target=run_send, args=("first",))
        second_thread = threading.Thread(target=run_send, args=("second",))
        with patch.object(ProspectMailer, "plan", plan_then_hold_the_locks):
            first_thread.start()
            self.assertTrue(first_has_claimed.wait(WAIT_SECONDS))
            second_thread.start()
            second_thread.join(WAIT_SECONDS)
            second_has_finished.set()
            first_thread.join(WAIT_SECONDS)

        self.assertEqual(len(reports["first"].sent), 5)
        self.assertEqual(reports["second"].sent, [])
        self.assertIsNone(reports["second"].mailing)
        self.assertEqual(Mailing.objects.count(), 1)
        self.assertEqual(
            sorted(message.to[0] for message in mail.outbox),
            sorted(prospect.email for prospect in prospects),
        )
