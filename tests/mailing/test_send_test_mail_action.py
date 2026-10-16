from unittest.mock import patch

from django.contrib.messages import ERROR, SUCCESS, get_messages
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.models import Mailing, MailingDelivery, ProspectEvent
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class SendTestMailActionTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user()
        self.client.force_login(self.staff_user)
        self.first_prospect = ProspectFactory(first_name="Ada")
        self.second_prospect = ProspectFactory(first_name="Grace")

    def post_step(self, step: str, **extra_fields: str):
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [
                    str(self.first_prospect.pk),
                    str(self.second_prospect.pk),
                ],
                "is_newsletter": "on",
                "step": step,
                "subject": "Hello {{ first_name }}",
                "body": "Dear {{ first_name }}",
                **extra_fields,
            },
        )

    def messages_of(self, response) -> list:
        return list(get_messages(response.wsgi_request))

    def test_the_test_step_sends_one_mail_to_the_staff_member_and_shows_the_preview_again(
        self,
    ) -> None:
        response = self.post_step("test", preview_prospect=str(self.second_prospect.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Step 2 of 2")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.staff_user.email])
        self.assertEqual(mail.outbox[0].subject, "[Test] Hello Grace")
        messages = self.messages_of(response)
        self.assertEqual(messages[0].level, SUCCESS)
        self.assertEqual(messages[0].message, f"A test was sent to {self.staff_user.email}.")

    def test_a_test_writes_nothing(self) -> None:
        self.post_step("test", preview_prospect=str(self.first_prospect.pk))

        self.assertEqual(Mailing.objects.count(), 0)
        self.assertEqual(MailingDelivery.objects.count(), 0)
        self.assertEqual(ProspectEvent.objects.count(), 0)
        self.first_prospect.refresh_from_db()
        self.assertIsNone(self.first_prospect.last_mailed_at)

    def test_a_tampered_prospect_falls_back_to_the_first_recipient(self) -> None:
        response = self.post_step("test", preview_prospect="not-a-prospect")

        first_recipient = response.context["preview_prospect"]
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f"[Test] Hello {first_recipient.first_name}")

    def test_the_preview_page_offers_the_test_button(self) -> None:
        response = self.post_step("preview")

        self.assertContains(response, 'name="step" value="test"')
        self.assertContains(response, "Send a test to me")

    def test_an_account_without_an_email_address_gets_an_error(self) -> None:
        self.staff_user.email = ""
        self.staff_user.save()

        response = self.post_step("test")

        self.assertEqual(len(mail.outbox), 0)
        messages = self.messages_of(response)
        self.assertEqual(messages[0].level, ERROR)
        self.assertIn("no email address", messages[0].message)

    def test_a_bad_button_link_goes_back_to_the_compose_page_and_sends_nothing(self) -> None:
        response = self.post_step("test", body='{% button "Book" first_name %}')

        self.assertContains(response, "Step 1 of 2")
        self.assertEqual(len(mail.outbox), 0)

    def test_a_mail_server_error_is_reported_without_its_text(self) -> None:
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=ConnectionRefusedError("secret reply")
        ):
            response = self.post_step("test")

        self.assertEqual(response.status_code, 200)
        messages = self.messages_of(response)
        self.assertEqual(messages[0].level, ERROR)
        self.assertEqual(
            messages[0].message, "The test could not be sent. Check the mail settings."
        )
        self.assertNotContains(response, "secret reply")

    @override_settings(OUTREACH_DISPATCH="celery")
    def test_a_test_is_sent_inline_in_celery_mode(self) -> None:
        self.post_step("test")

        self.assertEqual(len(mail.outbox), 1)

    def test_without_the_change_permission_nothing_is_sent(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

        self.post_step("test")

        self.assertEqual(len(mail.outbox), 0)
