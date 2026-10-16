from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from outreach.models import Mailing, MailingDelivery
from outreach.services.mailing import ProspectMailer
from outreach.services.scheduling import MailingScheduler
from outreach.tasks import deliver_mail
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery"
)
class CancelScheduledMailingTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.scheduler = MailingScheduler(ProspectMailer(MAIL_BASE_URL, "staff"))
        self.mailing = self.scheduler.schedule(
            [ProspectFactory()],
            "Subject",
            "<p>Body</p>",
            send_at=timezone.now() + timedelta(hours=2),
        ).mailing

    def test_a_mailing_that_has_not_started_is_deleted_with_its_deliveries(self) -> None:
        self.assertTrue(self.scheduler.cancel(self.mailing))

        self.assertFalse(Mailing.objects.exists())
        self.assertFalse(MailingDelivery.objects.exists())

    def test_a_mailing_that_has_started_is_kept(self) -> None:
        with (
            patch.object(deliver_mail, "apply_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.scheduler.start(self.mailing)

        self.assertFalse(self.scheduler.cancel(self.mailing))

        self.assertTrue(Mailing.objects.filter(pk=self.mailing.pk).exists())
        self.assertTrue(MailingDelivery.objects.exists())
