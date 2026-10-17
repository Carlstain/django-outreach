import json
from smtplib import SMTPRecipientsRefused
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import (
    outreach_mailing_change_url,
    outreach_prospect_change_url,
    outreach_prospect_export_data_url,
)

PERMISSIONS = ["view_prospect", "view_mailing"]


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class FailureLabelsAdminTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(PERMISSIONS))
        self.prospect = ProspectFactory(email="private.person@example.org")
        mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        queued_mailing = mailer.queue([self.prospect], "Subject", "<p>Body</p>", "", True)
        self.mailing = queued_mailing.mailing
        refusal = SMTPRecipientsRefused({self.prospect.email: (550, b"mailbox unavailable")})
        with patch.object(EmailMultiAlternatives, "send", side_effect=refusal):
            mailer.deliver(queued_mailing.deliveries[0].pk)

    def test_the_prospect_timeline_shows_the_label_and_never_the_server_reply(self) -> None:
        response = self.client.get(outreach_prospect_change_url(self.prospect.pk))

        self.assertContains(response, "The mail server refused it")
        self.assertNotContains(response, "mailbox unavailable")

    def test_the_dashboard_shows_the_label_and_never_the_server_reply(self) -> None:
        response = self.client.get("/outreach/")

        self.assertContains(response, "The mail server refused it")
        self.assertNotContains(response, "mailbox unavailable")

    def test_the_mailing_page_shows_the_label(self) -> None:
        response = self.client.get(outreach_mailing_change_url(self.mailing.pk))

        self.assertContains(response, "The mail server refused it")
        self.assertNotContains(response, "mailbox unavailable")

    def test_the_data_download_holds_the_kind_and_not_the_server_reply(self) -> None:
        response = self.client.get(outreach_prospect_export_data_url(self.prospect.pk))

        data = json.loads(response.content)
        self.assertEqual([delivery["failure"] for delivery in data["deliveries"]], ["refused"])
        self.assertEqual([event["detail"] for event in data["events"]], ["refused"])
        self.assertNotIn("mailbox unavailable", response.content.decode())
