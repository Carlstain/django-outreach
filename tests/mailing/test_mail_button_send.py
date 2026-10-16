from django.core import mail
from django.test import override_settings

from outreach.choices import EventKind, FailureKind
from outreach.models import ProspectEvent
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachMailTagTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailButtonSendTests(OutreachMailTagTestCase):
    def test_an_empty_or_invalid_computed_link_fails_only_that_recipient(self) -> None:
        links = {
            "Ada": "https://example.org/ada",
            "Empty": "",
            "Script": "javascript:alert(1)",
        }
        self.register_tag(lambda prospect: links[prospect.first_name], "booking_url")
        good = ProspectFactory(first_name="Ada")
        empty = ProspectFactory(first_name="Empty")
        script = ProspectFactory(first_name="Script")

        report = ProspectMailer(MAIL_BASE_URL, "staff").send(
            [good, empty, script], "Hello", '<p>{% button "Book" booking_url %}</p>'
        )

        self.assertEqual(report.sent, [good])
        self.assertEqual(report.failed, [empty, script])
        self.assertEqual([message.to for message in mail.outbox], [[good.email]])
        for failed_prospect in (empty, script):
            failed_prospect.refresh_from_db()
            self.assertIsNone(failed_prospect.last_mailed_at)
            failure = ProspectEvent.objects.get(
                prospect=failed_prospect, kind=EventKind.MAIL_FAILED
            )
            self.assertEqual(failure.detail, FailureKind.CONTENT)
