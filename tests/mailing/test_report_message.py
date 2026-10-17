from datetime import datetime, timezone

from django.contrib.messages import SUCCESS, WARNING
from django.utils import translation

from outreach.choices import SkipReason
from outreach.models import Mailing
from outreach.services.mailing import MailReport, SkippedProspect
from outreach.sites import outreach_site
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory


class ReportMessageTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospects = ProspectFactory.build_batch(3)
        language = translation.override("en")
        language.__enter__()
        self.addCleanup(language.__exit__, None, None, None)

    def message(self, report: MailReport) -> tuple[str, int]:
        return outreach_site.report_message(report)

    def test_a_scheduled_report_names_the_time_and_the_skipped_count(self) -> None:
        skipped = [SkippedProspect(self.prospects[2], SkipReason.COOLDOWN)]
        mailing = Mailing(scheduled_for=datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc))
        report = MailReport(mailing=mailing, scheduled=self.prospects[:2], skipped=skipped)

        text, level = self.message(report)

        self.assertRegex(text, r"^2 scheduled for .+, 1 skipped\.$")
        self.assertEqual(level, SUCCESS)

    def test_a_queued_report_names_the_queued_and_skipped_counts(self) -> None:
        text, level = self.message(MailReport(queued=self.prospects[:2]))

        self.assertEqual(text, "2 queued, 0 skipped.")
        self.assertEqual(level, SUCCESS)

    def test_a_sent_report_is_a_success_when_nothing_failed(self) -> None:
        text, level = self.message(MailReport(sent=self.prospects))

        self.assertEqual(text, "3 sent, 0 skipped, 0 failed.")
        self.assertEqual(level, SUCCESS)

    def test_a_sent_report_is_a_warning_when_something_failed(self) -> None:
        text, level = self.message(
            MailReport(sent=self.prospects[:2], failed=self.prospects[2:])
        )

        self.assertEqual(text, "2 sent, 0 skipped, 1 failed.")
        self.assertEqual(level, WARNING)
