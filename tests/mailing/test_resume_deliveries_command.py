from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.models import MailingDelivery
from outreach.services.mailing import ProspectMailer
from outreach.tasks import deliver_mail
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class ResumeDeliveriesCommandTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        queued_mailing = ProspectMailer(MAIL_BASE_URL, "staff").queue(
            [ProspectFactory(), ProspectFactory(), ProspectFactory()],
            "Subject",
            "<p>Body</p>",
            "",
            True,
        )
        self.stale, self.stale_but_sent, self.fresh = queued_mailing.deliveries
        long_ago = timezone.now() - timedelta(hours=2)
        MailingDelivery.objects.filter(pk__in=[self.stale.pk, self.stale_but_sent.pk]).update(
            updated_at=long_ago
        )
        MailingDelivery.objects.filter(pk=self.stale_but_sent.pk).update(
            status=DeliveryStatus.SENT
        )
        publisher = patch.object(deliver_mail, "apply_async")
        self.apply_async = publisher.start()
        self.addCleanup(publisher.stop)

    def test_only_stale_pending_deliveries_are_queued_again(self) -> None:
        output = StringIO()

        with self.captureOnCommitCallbacks(execute=True):
            call_command("outreach_resume_deliveries", "--older-than", "30", stdout=output)

        self.apply_async.assert_called_once()
        self.assertEqual(self.apply_async.call_args.kwargs["args"], [str(self.stale.pk)])
        self.assertIn("Deliveries queued: 1.", output.getvalue())

    def test_dry_run_counts_and_queues_nothing(self) -> None:
        output = StringIO()

        with self.captureOnCommitCallbacks(execute=True):
            call_command("outreach_resume_deliveries", "--dry-run", stdout=output)

        self.apply_async.assert_not_called()
        self.assertIn("Stale deliveries: 1.", output.getvalue())
