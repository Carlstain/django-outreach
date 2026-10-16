from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from outreach.models import Mailing, MailingDelivery
from outreach.tasks import deliver_mail
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory


class CancelScheduledMailingTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
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
