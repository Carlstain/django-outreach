from django.core import mail
from django.test import override_settings

from outreach.choices import ProspectStatus, SkipReason
from outreach.models import Mailing, Prospect
from outreach.services.mailing import ProspectMailer
from outreach.services.unsubscribe import SuppressionList
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory, UserFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailNoticeSendTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")

    def test_a_notice_skips_prospects_who_are_not_members(self) -> None:
        member = ProspectFactory(user=UserFactory())
        stranger = ProspectFactory()

        report = self.mailer.send(
            [member, stranger], "Terms", "<p>Body</p>", is_newsletter=False
        )

        self.assertEqual(report.sent, [member])
        self.assertEqual(
            [(skipped.prospect, skipped.reason) for skipped in report.skipped],
            [(stranger, SkipReason.NOT_MEMBER)],
        )
        self.assertEqual([message.to for message in mail.outbox], [[member.email]])
        self.assertEqual(report.mailing.skipped_reasons["not_member"], 1)

    def test_a_notice_still_reaches_members_who_unsubscribed_or_are_suppressed(self) -> None:
        unsubscribed_member = ProspectFactory(
            user=UserFactory(), status=ProspectStatus.UNSUBSCRIBED
        )
        suppressed_member = ProspectFactory(user=UserFactory())
        SuppressionList().add(suppressed_member.email)

        report = self.mailer.send(
            [unsubscribed_member, suppressed_member],
            "Terms",
            "<p>Body</p>",
            is_newsletter=False,
        )

        self.assertEqual(report.sent, [unsubscribed_member, suppressed_member])
        self.assertEqual(report.skipped, [])
        unsubscribed_member.refresh_from_db()
        self.assertEqual(unsubscribed_member.status, ProspectStatus.UNSUBSCRIBED)

    def test_a_notice_never_changes_who_is_unsubscribed(self) -> None:
        member = ProspectFactory(user=UserFactory(), status=ProspectStatus.UNSUBSCRIBED)

        self.mailer.send([member], "Terms", "<p>Body</p>", is_newsletter=False)

        self.assertEqual(
            Prospect.objects.get(pk=member.pk).status, ProspectStatus.UNSUBSCRIBED
        )

    def test_a_newsletter_keeps_its_skip_rules_and_reaches_non_members(self) -> None:
        stranger = ProspectFactory()
        unsubscribed = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)
        suppressed = ProspectFactory()
        SuppressionList().add(suppressed.email)

        report = self.mailer.send(
            [stranger, unsubscribed, suppressed], "News", "<p>Body</p>", is_newsletter=True
        )

        self.assertEqual(report.sent, [stranger])
        self.assertEqual(
            {skipped.prospect: skipped.reason for skipped in report.skipped},
            {
                unsubscribed: SkipReason.UNSUBSCRIBED,
                suppressed: SkipReason.SUPPRESSED,
            },
        )

    def test_the_mailing_records_its_type(self) -> None:
        member = ProspectFactory(user=UserFactory())
        self.mailer.send([member], "Terms", "<p>Body</p>", is_newsletter=False)

        self.assertFalse(Mailing.objects.get().is_newsletter)
