from smtplib import SMTPRecipientsRefused
from unittest.mock import patch
from uuid import uuid4

from django.core.mail import EmailMultiAlternatives
from django.test import override_settings

from outreach.choices import DeliveryStatus, EventKind
from outreach.models import MailingDelivery, ProspectEvent
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import MailingFactory, ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_mailing_change_url, outreach_mailing_retry_url

RETRY_PERMISSIONS = ["view_prospect", "view_mailing", "change_prospect"]


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailingRetryAdminTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(RETRY_PERMISSIONS))
        self.failed_prospect = ProspectFactory(first_name="Bruno", last_name="Petit")
        self.sent_prospect = ProspectFactory(first_name="Alice", last_name="Martin")
        self.pending_prospect = ProspectFactory(first_name="Chloe", last_name="Durand")
        self.skipped_prospect = ProspectFactory(first_name="Denis", last_name="Roux")
        mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        queued_mailing = mailer.queue(
            [self.failed_prospect, self.sent_prospect, self.pending_prospect],
            "Subject",
            "<p>Body</p>",
            "",
            True,
        )
        self.mailing = queued_mailing.mailing
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
        ):
            mailer.deliver(queued_mailing.deliveries[0].pk)
        mailer.deliver(queued_mailing.deliveries[1].pk)
        MailingDelivery.objects.create(
            mailing=self.mailing,
            prospect=self.skipped_prospect,
            status=DeliveryStatus.SKIPPED,
        )
        self.failed_delivery = queued_mailing.deliveries[0]

    def test_detail_lists_pending_sent_and_failed_deliveries_but_not_skipped_ones(
        self,
    ) -> None:
        response = self.client.get(outreach_mailing_change_url(self.mailing.pk))

        self.assertContains(response, "Bruno Petit")
        self.assertContains(response, "Alice Martin")
        self.assertContains(response, "Chloe Durand")
        self.assertNotContains(response, "Denis Roux")

    def test_detail_does_not_show_the_raw_delivery_error(self) -> None:
        self.failed_delivery.refresh_from_db()
        self.assertTrue(self.failed_delivery.last_error)

        response = self.client.get(outreach_mailing_change_url(self.mailing.pk))

        self.assertNotContains(response, self.failed_delivery.last_error)
        self.assertContains(response, "The mail could not be delivered.")

    def test_a_mailing_without_deliveries_still_lists_its_events(self) -> None:
        legacy_mailing = MailingFactory()
        legacy_prospect = ProspectFactory(first_name="Emma", last_name="Blanc")
        ProspectEvent.record(
            legacy_prospect, EventKind.MAILED, "staff", "Subject", mailing=legacy_mailing
        )

        response = self.client.get(outreach_mailing_change_url(legacy_mailing.pk))

        self.assertContains(response, "Emma Blanc")
        self.assertNotContains(response, outreach_mailing_retry_url(legacy_mailing.pk))

    def test_retry_buttons_are_shown_with_the_change_prospect_permission(self) -> None:
        response = self.client.get(outreach_mailing_change_url(self.mailing.pk))

        self.assertContains(response, outreach_mailing_retry_url(self.mailing.pk))
        self.assertContains(response, "Retry all failed (1)")

    def test_retry_buttons_are_hidden_without_the_change_prospect_permission(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect", "view_mailing"]))

        response = self.client.get(outreach_mailing_change_url(self.mailing.pk))

        self.assertNotContains(response, outreach_mailing_retry_url(self.mailing.pk))

    def test_retrying_without_the_change_prospect_permission_is_refused(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect", "view_mailing"]))

        response = self.client.post(outreach_mailing_retry_url(self.mailing.pk))

        self.assertEqual(response.status_code, 403)
        self.failed_delivery.refresh_from_db()
        self.assertEqual(self.failed_delivery.status, DeliveryStatus.FAILED)

    def test_retry_only_accepts_post(self) -> None:
        response = self.client.get(outreach_mailing_retry_url(self.mailing.pk))

        self.assertEqual(response.status_code, 405)

    def test_retrying_one_delivery_sends_it_and_reports_the_result(self) -> None:
        response = self.client.post(
            outreach_mailing_retry_url(self.mailing.pk),
            {"delivery": str(self.failed_delivery.pk)},
            follow=True,
        )

        self.assertRedirects(response, outreach_mailing_change_url(self.mailing.pk))
        self.assertContains(response, "1 sent, 0 skipped, 0 failed.")
        self.failed_delivery.refresh_from_db()
        self.assertEqual(self.failed_delivery.status, DeliveryStatus.SENT)

    def test_retrying_without_a_delivery_retries_every_failed_one(self) -> None:
        response = self.client.post(outreach_mailing_retry_url(self.mailing.pk), follow=True)

        self.assertContains(response, "1 sent, 0 skipped, 0 failed.")
        self.mailing.refresh_from_db()
        self.assertEqual(self.mailing.failed_count, 0)

    def test_an_unknown_delivery_id_is_a_404(self) -> None:
        response = self.client.post(
            outreach_mailing_retry_url(self.mailing.pk), {"delivery": "not-a-uuid"}
        )

        self.assertEqual(response.status_code, 404)

    def test_an_unknown_mailing_is_a_404(self) -> None:
        response = self.client.post(outreach_mailing_retry_url(uuid4()))

        self.assertEqual(response.status_code, 404)

    @override_settings(OUTREACH_BASE_URL=None)
    def test_retrying_without_a_base_url_changes_nothing(self) -> None:
        response = self.client.post(outreach_mailing_retry_url(self.mailing.pk), follow=True)

        self.assertContains(response, "OUTREACH_BASE_URL is not set")
        self.failed_delivery.refresh_from_db()
        self.assertEqual(self.failed_delivery.status, DeliveryStatus.FAILED)
