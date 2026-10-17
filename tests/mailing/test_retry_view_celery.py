from smtplib import SMTPRecipientsRefused
from unittest.mock import patch

from django.core.mail import EmailMultiAlternatives
from django.urls import reverse

from outreach.models import MailingDelivery
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user


class RetryViewCeleryTests(CeleryMailTestCase):
    def test_a_celery_retry_reports_the_queued_and_skipped_counts(self) -> None:
        self.client.force_login(
            create_outreach_staff_user(["view_prospect", "view_mailing", "change_prospect"])
        )
        queued_mailing = self.mailer.queue(
            [ProspectFactory()], "Subject", "<p>Body</p>", "", True
        )
        with patch.object(
            EmailMultiAlternatives, "send", side_effect=SMTPRecipientsRefused({})
        ):
            self.mailer.deliver(queued_mailing.deliveries[0].pk)
        retry_url = reverse(
            "outreach_admin:outreach_mailing_retry", args=[queued_mailing.mailing.pk]
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(retry_url, follow=True)

        self.assertContains(response, "1 queued, 0 skipped.")
        self.assertEqual(
            MailingDelivery.objects.get(mailing=queued_mailing.mailing).status, "pending"
        )
