from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.models import Mailing
from outreach.services.mailing import ProspectMailer
from outreach.services.scheduling import MailingScheduler, SchedulingUnavailable
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery"
)
class ScheduleMailingTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.scheduler = MailingScheduler(ProspectMailer(MAIL_BASE_URL, "staff"))
        self.send_at = timezone.now() + timedelta(hours=2)

    def test_the_mailing_is_stored_with_scheduled_deliveries_and_nobody_is_claimed(
        self,
    ) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        report = self.scheduler.schedule(
            prospects, "Subject", "<p>Body</p>", send_at=self.send_at
        )

        self.assertEqual(report.scheduled, prospects)
        mailing = Mailing.objects.get()
        self.assertEqual(mailing.scheduled_for, self.send_at)
        self.assertEqual(
            list(mailing.deliveries.values_list("status", flat=True)),
            [DeliveryStatus.SCHEDULED, DeliveryStatus.SCHEDULED],
        )
        for prospect in prospects:
            prospect.refresh_from_db()
            self.assertIsNone(prospect.last_mailed_at)

    def test_recipients_are_chosen_now_and_skipped_ones_are_counted(self) -> None:
        recently_mailed = ProspectFactory(last_mailed_at=timezone.now())

        report = self.scheduler.schedule(
            [ProspectFactory(), recently_mailed],
            "Subject",
            "<p>Body</p>",
            send_at=self.send_at,
        )

        self.assertEqual(len(report.scheduled), 1)
        self.assertEqual([skipped.prospect for skipped in report.skipped], [recently_mailed])
        self.assertEqual(report.mailing.skipped_count, 1)

    def test_nobody_to_mail_stores_nothing(self) -> None:
        report = self.scheduler.schedule(
            [ProspectFactory(last_mailed_at=timezone.now())],
            "Subject",
            "<p>Body</p>",
            send_at=self.send_at,
        )

        self.assertIsNone(report.mailing)
        self.assertFalse(Mailing.objects.exists())

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_scheduling_is_refused_in_sync_mode(self) -> None:
        with self.assertRaises(SchedulingUnavailable):
            self.scheduler.schedule(
                [ProspectFactory()], "Subject", "<p>Body</p>", send_at=self.send_at
            )

        self.assertFalse(Mailing.objects.exists())
