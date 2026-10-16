from datetime import timedelta
from smtplib import SMTPRecipientsRefused
from unittest.mock import patch

from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus, ProspectStatus
from outreach.models import MailingDelivery, Prospect
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailRetryTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.first_prospect = ProspectFactory()
        self.second_prospect = ProspectFactory()
        queued_mailing = self.mailer.queue(
            [self.first_prospect, self.second_prospect], "Subject", "<p>Body</p>", "", True
        )
        self.mailing = queued_mailing.mailing
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
        ):
            for delivery in queued_mailing.deliveries:
                self.mailer.deliver(delivery.pk)
        self.mailing.refresh_from_db()

    def delivery_of(self, prospect: Prospect) -> MailingDelivery:
        return MailingDelivery.objects.get(mailing=self.mailing, prospect=prospect)

    def test_a_failed_delivery_is_sent_again(self) -> None:
        self.assertEqual(self.mailing.failed_count, 2)

        report = self.mailer.retry(self.mailing)

        self.assertEqual(report.sent, [self.first_prospect, self.second_prospect])
        self.assertEqual(len(mail.outbox), 2)
        self.mailing.refresh_from_db()
        self.assertEqual(self.mailing.failed_count, 0)
        self.assertEqual(self.mailing.sent_count, 2)
        self.assertEqual(self.delivery_of(self.first_prospect).status, DeliveryStatus.SENT)
        self.assertEqual(self.delivery_of(self.first_prospect).failure_kind, "")

    def test_only_the_given_deliveries_are_retried(self) -> None:
        chosen = self.delivery_of(self.second_prospect)

        report = self.mailer.retry(self.mailing, chosen.pk)

        self.assertEqual(report.sent, [self.second_prospect])
        self.assertEqual(len(mail.outbox), 1)
        self.mailing.refresh_from_db()
        self.assertEqual(self.mailing.failed_count, 1)
        self.assertEqual(self.delivery_of(self.first_prospect).status, DeliveryStatus.FAILED)

    def test_deliveries_that_did_not_fail_are_not_reopened(self) -> None:
        sent_prospect = ProspectFactory()
        pending_prospect = ProspectFactory()
        queued_mailing = self.mailer.queue(
            [sent_prospect, pending_prospect], "Other", "<p>Body</p>", "", True
        )
        self.mailer.deliver(queued_mailing.deliveries[0].pk)

        report = self.mailer.retry(queued_mailing.mailing)

        self.assertEqual(report.sent, [])
        self.assertEqual(len(mail.outbox), 1)
        statuses = {
            delivery.prospect_id: delivery.status
            for delivery in queued_mailing.mailing.deliveries.all()
        }
        self.assertEqual(
            statuses,
            {
                sent_prospect.pk: DeliveryStatus.SENT,
                pending_prospect.pk: DeliveryStatus.PENDING,
            },
        )

    def test_a_prospect_who_unsubscribed_since_the_failure_is_skipped(self) -> None:
        self.first_prospect.status = ProspectStatus.UNSUBSCRIBED
        self.first_prospect.save()

        report = self.mailer.retry(self.mailing, self.delivery_of(self.first_prospect).pk)

        self.assertEqual(
            [skipped.prospect for skipped in report.skipped], [self.first_prospect]
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.delivery_of(self.first_prospect).status, DeliveryStatus.SKIPPED)

    def test_a_failure_on_retry_restores_the_claim_and_counts_failed_again(self) -> None:
        self.first_prospect.refresh_from_db()
        last_mailed_before_retry = self.first_prospect.last_mailed_at

        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
        ):
            report = self.mailer.retry(self.mailing)

        self.assertEqual(report.failed, [self.first_prospect, self.second_prospect])
        self.mailing.refresh_from_db()
        self.first_prospect.refresh_from_db()
        self.assertEqual(self.mailing.failed_count, 2)
        self.assertEqual(self.first_prospect.last_mailed_at, last_mailed_before_retry)
        self.assertEqual(self.delivery_of(self.first_prospect).status, DeliveryStatus.FAILED)

    def test_the_resend_cooldown_does_not_block_a_retry(self) -> None:
        self.first_prospect.last_mailed_at = timezone.now() - timedelta(hours=1)
        self.first_prospect.save()

        report = self.mailer.retry(self.mailing, self.delivery_of(self.first_prospect).pk)

        self.assertEqual(report.sent, [self.first_prospect])
        self.assertEqual(len(mail.outbox), 1)
