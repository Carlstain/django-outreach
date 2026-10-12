from django.core import mail
from django.test import override_settings

from outreach.choices import EventKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachMailTagTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailTagSendTests(OutreachMailTagTestCase):
    def test_a_raising_tag_fails_only_that_recipient(self) -> None:
        def fragile(prospect: Prospect) -> str:
            if prospect.first_name == "Broken":
                raise ValueError("tag exploded")
            return prospect.first_name

        self.register_tag(fragile, "fragile")
        first_good = ProspectFactory(first_name="Ada")
        broken = ProspectFactory(first_name="Broken")
        second_good = ProspectFactory(first_name="Grace")

        report = ProspectMailer(MAIL_BASE_URL, "staff").send(
            [first_good, broken, second_good], "Hello {% fragile %}", "<p>Body</p>"
        )

        self.assertEqual(report.sent, [first_good, second_good])
        self.assertEqual(report.failed, [broken])
        self.assertEqual(
            sorted(message.subject for message in mail.outbox), ["Hello Ada", "Hello Grace"]
        )
        broken.refresh_from_db()
        self.assertIsNone(broken.last_mailed_at)
        self.assertEqual(broken.status, ProspectStatus.PROSPECT)
        failure = ProspectEvent.objects.get(prospect=broken, kind=EventKind.MAIL_FAILED)
        self.assertIn("tag exploded", failure.detail)
        self.assertEqual(report.mailing.failed_count, 1)
        self.assertEqual(report.mailing.sent_count, 2)
