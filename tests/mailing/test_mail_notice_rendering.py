from django.core import mail
from django.test import override_settings

from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory, UserFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailNoticeRenderingTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.member = ProspectFactory(user=UserFactory())

    def test_a_newsletter_ends_with_the_unsubscribe_footer_in_both_parts(self) -> None:
        rendered = self.mailer.render(self.member, "Hello", "<p>Body</p>", is_newsletter=True)

        unsubscribe_url = self.mailer.unsubscribe_url(self.member)
        self.assertIn("You receive this message because", rendered.html)
        self.assertIn(f'href="{unsubscribe_url}"', rendered.html)
        self.assertIn(unsubscribe_url, rendered.text)

    def test_a_notice_has_no_unsubscribe_footer_in_either_part(self) -> None:
        rendered = self.mailer.render(self.member, "Hello", "<p>Body</p>", is_newsletter=False)

        unsubscribe_url = self.mailer.unsubscribe_url(self.member)
        self.assertNotIn("You receive this message because", rendered.html)
        self.assertNotIn("Unsubscribe", rendered.html)
        self.assertNotIn(unsubscribe_url, rendered.html)
        self.assertNotIn("nsubscribe", rendered.text)
        self.assertIn("Body", rendered.html)
        self.assertIn("Body", rendered.text)

    def test_a_mail_is_a_newsletter_unless_told_otherwise(self) -> None:
        rendered = self.mailer.render(self.member, "Hello", "<p>Body</p>")

        self.assertIn(self.mailer.unsubscribe_url(self.member), rendered.html)

    def test_unsubscribe_headers_are_sent_with_a_newsletter_only(self) -> None:
        self.mailer.send([self.member], "Newsletter", "<p>Body</p>", is_newsletter=True)
        other_member = ProspectFactory(user=UserFactory())
        self.mailer.send([other_member], "Notice", "<p>Body</p>", is_newsletter=False)

        newsletter_message, notice_message = mail.outbox
        self.assertEqual(
            newsletter_message.extra_headers["List-Unsubscribe"],
            f"<{self.mailer.unsubscribe_url(self.member)}>",
        )
        self.assertEqual(
            newsletter_message.extra_headers["List-Unsubscribe-Post"],
            "List-Unsubscribe=One-Click",
        )
        self.assertNotIn("List-Unsubscribe", notice_message.extra_headers)
        self.assertNotIn("List-Unsubscribe-Post", notice_message.extra_headers)
