from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.messages import ERROR, get_messages
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings
from django.urls import resolve
from django.utils import timezone

from outreach.choices import EventKind, ProspectStatus, SkipReason
from outreach.models import Mailing, Prospect, ProspectEvent
from outreach.services.mailing import ProspectMailer
from outreach.services.unsubscribe import SuppressionList, UnsubscribeTokens
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url


class MailAbort(BaseException):
    pass


BASE_URL = "https://outreach.example.test"
SUBJECT = "Welcome to the platform"
BODY = "Hello,\n\nJoin us."


@override_settings(OUTREACH_BASE_URL=BASE_URL, OUTREACH_LANGUAGE="en")
class SendMailActionTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user()
        self.client.force_login(self.staff_user)

    def post_action(self, prospects: list, **extra_fields: str) -> object:
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [str(prospect.pk) for prospect in prospects],
                **extra_fields,
            },
        )

    def post_send(self, prospects: list) -> object:
        return self.post_action(prospects, step="send", subject=SUBJECT, body=BODY)

    def test_compose_then_preview_send_nothing(self) -> None:
        prospect = ProspectFactory()

        compose_response = self.post_action([prospect])
        preview_response = self.post_action(
            [prospect], step="preview", subject=SUBJECT, body=BODY
        )

        self.assertEqual(compose_response.status_code, 200)
        self.assertEqual(compose_response.context["plan"].recipients, [prospect])
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.context["preview_prospect"], prospect)
        self.assertEqual(len(mail.outbox), 0)
        prospect.refresh_from_db()
        self.assertIsNone(prospect.last_mailed_at)

    def test_edit_message_step_rerenders_compose_with_posted_values(self) -> None:
        prospect = ProspectFactory()

        response = self.post_action([prospect], step="compose", subject=SUBJECT, body=BODY)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outreach/admin/compose.html")
        self.assertNotIn("preview_prospect", response.context)
        self.assertEqual(response.context["form"]["subject"].value(), SUBJECT)
        self.assertEqual(response.context["form"]["body"].value(), BODY)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_preview_form_does_not_reach_preview(self) -> None:
        prospect = ProspectFactory()

        response = self.post_action([prospect], step="preview", subject="", body=BODY)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("preview_prospect", response.context)
        self.assertEqual(len(mail.outbox), 0)

    def test_send_delivers_mail_with_unsubscribe_link_and_headers(self) -> None:
        prospect = ProspectFactory()

        response = self.post_send([prospect])

        self.assertRedirects(
            response, outreach_prospect_changelist_url(), fetch_redirect_response=False
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [prospect.email])
        self.assertEqual(message.subject, SUBJECT)
        unsubscribe_url = message.extra_headers["List-Unsubscribe"].strip("<>")
        self.assertTrue(unsubscribe_url.startswith(BASE_URL))
        self.assertEqual(
            message.extra_headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click"
        )
        self.assertIn(unsubscribe_url, message.body)
        html_body = message.alternatives[0][0]
        self.assertIn(unsubscribe_url, html_body)
        token = resolve(urlsplit(unsubscribe_url).path).kwargs["token"]
        self.assertEqual(UnsubscribeTokens().resolve(token), prospect)

    def test_send_updates_status_timestamp_and_records_event(self) -> None:
        prospect = ProspectFactory()

        self.post_send([prospect])

        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.CONTACTED)
        self.assertIsNotNone(prospect.last_mailed_at)
        mailed_event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.MAILED)
        self.assertEqual(mailed_event.detail, SUBJECT)

    def test_send_skips_unsubscribed_suppressed_and_cooldown_prospects(self) -> None:
        eligible = ProspectFactory()
        unsubscribed = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)
        suppressed = ProspectFactory()
        SuppressionList().add(suppressed.email)
        cooling_down = ProspectFactory(last_mailed_at=timezone.now() - timedelta(hours=1))
        prospects = [eligible, unsubscribed, suppressed, cooling_down]

        compose_response = self.post_action(prospects)
        self.post_send(prospects)

        skipped_reasons = {
            skipped.prospect: skipped.reason
            for skipped in compose_response.context["plan"].skipped
        }
        self.assertEqual(
            skipped_reasons,
            {
                unsubscribed: SkipReason.UNSUBSCRIBED,
                suppressed: SkipReason.SUPPRESSED,
                cooling_down: SkipReason.COOLDOWN,
            },
        )
        self.assertEqual([message.to for message in mail.outbox], [[eligible.email]])

    @override_settings(OUTREACH_MAX_RECIPIENTS_PER_SEND=2)
    def test_send_stops_at_the_recipient_cap(self) -> None:
        prospects = [ProspectFactory() for _ in range(3)]

        compose_response = self.post_action(prospects)
        self.post_send(prospects)

        skipped = compose_response.context["plan"].skipped
        self.assertEqual([entry.reason for entry in skipped], [SkipReason.OVER_LIMIT])
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(OUTREACH_BASE_URL=None)
    def test_send_is_refused_when_base_url_is_unset(self) -> None:
        prospect = ProspectFactory()

        response = self.post_send([prospect])

        self.assertEqual(response.status_code, 302)
        levels = [message.level for message in get_messages(response.wsgi_request)]
        self.assertIn(ERROR, levels)
        self.assertEqual(len(mail.outbox), 0)
        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.PROSPECT)

    def test_select_across_sends_to_the_whole_filtered_set(self) -> None:
        prospects = [ProspectFactory() for _ in range(3)]
        across_fields = {"select_across": "1"}

        compose_response = self.post_action(prospects[:1], **across_fields)
        self.post_action(
            prospects[:1], step="preview", subject=SUBJECT, body=BODY, **across_fields
        )
        self.post_action(
            prospects[:1], step="send", subject=SUBJECT, body=BODY, **across_fields
        )

        self.assertEqual(compose_response.context["queryset_ids"], [str(prospects[0].pk)])
        self.assertEqual(compose_response.context["select_across"], 1)
        self.assertEqual(len(compose_response.context["plan"].recipients), 3)
        self.assertEqual(len(mail.outbox), 3)

    def test_page_selection_only_mails_the_selected_prospects(self) -> None:
        selected = [ProspectFactory(), ProspectFactory()]
        ProspectFactory()

        self.post_send(selected)

        self.assertEqual(
            sorted(message.to[0] for message in mail.outbox),
            sorted(prospect.email for prospect in selected),
        )

    def test_second_send_of_the_same_recipients_sends_nothing(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        self.post_send(prospects)
        self.post_send(prospects)

        self.assertEqual(len(mail.outbox), 2)

    def test_recipients_are_claimed_before_the_mail_is_sent(self) -> None:
        prospect = ProspectFactory()
        mailed_at_values = []

        def fake_send(message: EmailMultiAlternatives, fail_silently: bool = False) -> int:
            mailed_at_values.append(Prospect.objects.get(pk=prospect.pk).last_mailed_at)
            return 1

        with patch.object(
            EmailMultiAlternatives, "send", autospec=True, side_effect=fake_send
        ):
            self.post_send([prospect])

        self.assertEqual(len(mailed_at_values), 1)
        self.assertIsNotNone(mailed_at_values[0])

    def test_failed_recipient_is_recorded_and_the_others_are_still_sent(self) -> None:
        failing = ProspectFactory()
        working = ProspectFactory()

        def fake_send(message: EmailMultiAlternatives, fail_silently: bool = False) -> int:
            if message.to == [failing.email]:
                raise SMTPException("connection lost")
            return 1

        with patch.object(
            EmailMultiAlternatives, "send", autospec=True, side_effect=fake_send
        ):
            self.post_send([failing, working])

        failing.refresh_from_db()
        working.refresh_from_db()
        self.assertIsNone(failing.last_mailed_at)
        self.assertEqual(failing.status, ProspectStatus.PROSPECT)
        self.assertTrue(
            ProspectEvent.objects.filter(prospect=failing, kind=EventKind.MAIL_FAILED).exists()
        )
        self.assertIsNotNone(working.last_mailed_at)
        self.assertEqual(working.status, ProspectStatus.CONTACTED)

    def test_send_returning_zero_counts_as_a_failure(self) -> None:
        prospect = ProspectFactory()

        with patch.object(EmailMultiAlternatives, "send", autospec=True, return_value=0):
            self.post_send([prospect])

        prospect.refresh_from_db()
        self.assertIsNone(prospect.last_mailed_at)
        self.assertTrue(
            ProspectEvent.objects.filter(
                prospect=prospect, kind=EventKind.MAIL_FAILED
            ).exists()
        )

    def test_prospect_unsubscribed_during_the_send_is_not_overwritten(self) -> None:
        prospect = ProspectFactory()
        original_send = EmailMultiAlternatives.send

        def unsubscribe_then_send(
            message: EmailMultiAlternatives, fail_silently: bool = False
        ) -> int:
            Prospect.objects.filter(pk=prospect.pk).update(status=ProspectStatus.UNSUBSCRIBED)
            return original_send(message, fail_silently)

        with patch.object(
            EmailMultiAlternatives, "send", autospec=True, side_effect=unsubscribe_then_send
        ):
            self.post_send([prospect])

        prospect.refresh_from_db()
        self.assertEqual(prospect.status, ProspectStatus.UNSUBSCRIBED)

    def test_each_recipient_receives_their_own_name_in_every_part(self) -> None:
        alice = ProspectFactory(first_name="Alice")
        bruno = ProspectFactory(first_name="Bruno")

        self.post_action(
            [alice, bruno],
            step="send",
            subject="Hello {{ first_name }}",
            body="<p>Dear {{ first_name }}</p>",
        )

        sent_by_address = {message.to[0]: message for message in mail.outbox}
        for prospect in (alice, bruno):
            message = sent_by_address[prospect.email]
            self.assertEqual(message.subject, f"Hello {prospect.first_name}")
            self.assertIn(f"Dear {prospect.first_name}", message.body)
            self.assertIn(f"Dear {prospect.first_name}", message.alternatives[0][0])
        self.assertNotIn("Bruno", sent_by_address[alice.email].body)

    def test_unknown_variable_keeps_the_user_on_compose_with_the_error(self) -> None:
        prospect = ProspectFactory()

        response = self.post_action(
            [prospect], step="send", subject=SUBJECT, body="<p>Hi {{ firstname }}</p>"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outreach/admin/compose.html")
        self.assertIn("firstname", " ".join(response.context["form"].errors["body"]))
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Mailing.objects.count(), 0)

    def test_send_creates_a_mailing_with_counts_and_skipped_reasons(self) -> None:
        sent_to = ProspectFactory()
        unsubscribed = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)
        cooling_down = ProspectFactory(last_mailed_at=timezone.now() - timedelta(hours=1))

        self.post_send([sent_to, unsubscribed, cooling_down])

        mailing = Mailing.objects.get()
        self.assertEqual(mailing.subject, SUBJECT)
        self.assertEqual(mailing.sender, self.staff_user.get_username())
        self.assertIn("Join us.", mailing.body_html)
        self.assertEqual(mailing.sent_count, 1)
        self.assertEqual(mailing.failed_count, 0)
        self.assertEqual(mailing.skipped_count, 2)
        recorded_reasons = {
            reason: count for reason, count in mailing.skipped_reasons.items() if count
        }
        self.assertEqual(
            recorded_reasons,
            {SkipReason.UNSUBSCRIBED.value: 1, SkipReason.COOLDOWN.value: 1},
        )

    def test_mailing_stores_the_subject_and_body_before_personalisation(self) -> None:
        prospect = ProspectFactory(first_name="Alice")

        self.post_action(
            [prospect],
            step="send",
            subject="Hi {{ first_name }}",
            body="<p>{{ first_name }}</p>",
        )

        mailing = Mailing.objects.get()
        self.assertEqual(mailing.subject, "Hi {{ first_name }}")
        self.assertIn("{{ first_name }}", mailing.body_html)
        self.assertNotIn("Alice", mailing.body_html)

    def test_failed_deliveries_are_counted_on_the_mailing(self) -> None:
        failing = ProspectFactory()
        working = ProspectFactory()

        def fake_send(message: EmailMultiAlternatives, fail_silently: bool = False) -> int:
            if message.to == [failing.email]:
                raise SMTPException("connection lost")
            return 1

        with patch.object(
            EmailMultiAlternatives, "send", autospec=True, side_effect=fake_send
        ):
            self.post_send([failing, working])

        mailing = Mailing.objects.get()
        self.assertEqual(mailing.sent_count, 1)
        self.assertEqual(mailing.failed_count, 1)

    def test_events_point_at_the_mailing(self) -> None:
        prospect = ProspectFactory()

        self.post_send([prospect])

        mailing = Mailing.objects.get()
        mailed_event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.MAILED)
        self.assertEqual(mailed_event.mailing, mailing)

    def test_failure_events_point_at_the_mailing(self) -> None:
        prospect = ProspectFactory()

        with patch.object(EmailMultiAlternatives, "send", autospec=True, return_value=0):
            self.post_send([prospect])

        failed_event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.MAIL_FAILED)
        self.assertEqual(failed_event.mailing, Mailing.objects.get())

    def test_deleting_the_mailing_keeps_the_prospect_timeline(self) -> None:
        prospect = ProspectFactory()
        self.post_send([prospect])

        Mailing.objects.get().delete()

        mailed_event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.MAILED)
        self.assertIsNone(mailed_event.mailing)

    def test_preview_can_be_rendered_as_another_recipient(self) -> None:
        alice = ProspectFactory(first_name="Alice")
        bruno = ProspectFactory(first_name="Bruno")
        fields = {
            "step": "preview",
            "subject": "Hello {{ first_name }}",
            "body": "<p>Dear {{ first_name }}</p>",
        }

        default_response = self.post_action([alice, bruno], **fields)
        first_recipient, other_recipient = default_response.context["plan"].recipients
        chosen_response = self.post_action(
            [alice, bruno], preview_prospect=str(other_recipient.pk), **fields
        )

        self.assertEqual(default_response.context["preview_prospect"], first_recipient)
        self.assertEqual(chosen_response.context["preview_prospect"], other_recipient)
        self.assertIn(
            f"Dear {other_recipient.first_name}", chosen_response.context["preview_html"]
        )
        self.assertEqual(
            chosen_response.context["preview_subject"],
            f"Hello {other_recipient.first_name}",
        )
        self.assertEqual(chosen_response.context_data["subject"], "Hello {{ first_name }}")
        self.assertEqual(len(chosen_response.context["preview_choices"]), 2)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_mailing_is_created_when_nobody_can_be_mailed(self) -> None:
        unsubscribed = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)

        self.post_send([unsubscribed])

        self.assertEqual(Mailing.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_failed_mailing_creation_rolls_the_claim_back(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]

        with (
            patch.object(Mailing.objects, "create", side_effect=RuntimeError("boom")),
            self.assertRaises(RuntimeError),
        ):
            self.post_send(prospects)

        for prospect in prospects:
            prospect.refresh_from_db()
            self.assertIsNone(prospect.last_mailed_at)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Mailing.objects.count(), 0)

    def test_unexpected_error_releases_unprocessed_recipients_and_saves_counts(self) -> None:
        prospects = [ProspectFactory(), ProspectFactory()]
        original_send = EmailMultiAlternatives.send
        sent_messages = []

        def send_first_then_abort(
            message: EmailMultiAlternatives, fail_silently: bool = False
        ) -> int:
            if sent_messages:
                raise MailAbort
            sent_messages.append(message.to[0])
            return original_send(message, fail_silently)

        with (
            patch.object(
                EmailMultiAlternatives,
                "send",
                autospec=True,
                side_effect=send_first_then_abort,
            ),
            self.assertRaises(MailAbort),
        ):
            self.post_send(prospects)

        mailing = Mailing.objects.get()
        last_mailed_by_email = {
            prospect.email: self.reload_last_mailed_at(prospect) for prospect in prospects
        }
        self.assertEqual(mailing.sent_count, 1)
        self.assertIsNotNone(last_mailed_by_email[sent_messages[0]])
        unsent_emails = [email for email in last_mailed_by_email if email != sent_messages[0]]
        self.assertIsNone(last_mailed_by_email[unsent_emails[0]])

    def reload_last_mailed_at(self, prospect: Prospect) -> object:
        return Prospect.objects.get(pk=prospect.pk).last_mailed_at

    def test_recipient_unsubscribed_mid_send_is_counted_as_skipped(self) -> None:
        first = ProspectFactory(created_at=timezone.now() - timedelta(days=2))
        second = ProspectFactory()
        original_send = EmailMultiAlternatives.send

        def unsubscribe_older_then_send(
            message: EmailMultiAlternatives, fail_silently: bool = False
        ) -> int:
            Prospect.objects.filter(pk=first.pk).update(status=ProspectStatus.UNSUBSCRIBED)
            return original_send(message, fail_silently)

        with patch.object(
            EmailMultiAlternatives,
            "send",
            autospec=True,
            side_effect=unsubscribe_older_then_send,
        ):
            self.post_send([first, second])

        mailing = Mailing.objects.get()
        self.assertEqual(mailing.sent_count, 1)
        self.assertEqual(mailing.skipped_count, 1)
        self.assertEqual(mailing.skipped_reasons[SkipReason.UNSUBSCRIBED.value], 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_tampered_preview_prospect_falls_back_to_the_first_recipient(self) -> None:
        recipients = [ProspectFactory(first_name="Alice"), ProspectFactory(first_name="Bruno")]
        outsider = ProspectFactory(
            first_name="Outsider",
            email="outsider@private.test",
            status=ProspectStatus.UNSUBSCRIBED,
        )
        unselected = ProspectFactory(first_name="Unselected", email="unselected@private.test")
        fields = {
            "step": "preview",
            "subject": "Hello {{ first_name }}",
            "body": "<p>Dear {{ first_name }}, {{ email }}</p>",
        }

        for tampered_value in (str(outsider.pk), str(unselected.pk), "not-a-uuid", ""):
            with self.subTest(preview_prospect=tampered_value):
                response = self.post_action(
                    recipients, preview_prospect=tampered_value, **fields
                )

                first_recipient = response.context["plan"].recipients[0]
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["preview_prospect"], first_recipient)
                self.assertIn(first_recipient.email, response.context["preview_html"])
                self.assertNotContains(response, "Outsider")
                self.assertNotContains(response, "Unselected")
                self.assertNotContains(response, "private.test")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(OUTREACH_LANGUAGE="fr")
    def test_compose_form_labels_have_no_colon_suffix(self) -> None:
        prospect = ProspectFactory()

        response = self.post_action([prospect])

        for bound_field in response.context["form"]:
            label_html = str(bound_field.label_tag())
            self.assertNotRegex(label_html, r":\s*</label>")

    def test_a_very_long_actor_is_truncated_to_the_stored_field_length(self) -> None:
        actor = "x" * 240 + "@example.test"
        prospect = ProspectFactory()
        mailer = ProspectMailer(BASE_URL, actor)

        report = mailer.send([prospect], SUBJECT, BODY)

        mailing = Mailing.objects.get()
        mailed_event = ProspectEvent.objects.get(prospect=prospect, kind=EventKind.MAILED)
        self.assertEqual(report.sent, [prospect])
        self.assertEqual(len(actor), 253)
        self.assertEqual(mailing.sender, actor[:150])
        self.assertEqual(mailed_event.actor, actor[:150])

    def test_a_very_long_actor_does_not_break_recording_an_event(self) -> None:
        actor = "y" * 254
        prospect = ProspectFactory()

        ProspectEvent.record(prospect, EventKind.EDITED, actor)

        self.assertEqual(ProspectEvent.objects.get(prospect=prospect).actor, "y" * 150)
