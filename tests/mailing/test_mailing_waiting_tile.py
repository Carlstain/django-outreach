from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from tests.base import OutreachTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory, create_outreach_staff_user
from tests.routes import outreach_mailing_change_url


@override_settings(
    OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery", OUTREACH_SEND_LIMIT_PER_HOUR=1
)
class MailingWaitingTileTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(["view_prospect", "view_mailing"]))
        self.mailing = MailingFactory()

    def open_mailing(self):
        return self.client.get(outreach_mailing_change_url(str(self.mailing.pk)))

    def test_tile_counts_waiting_deliveries(self) -> None:
        for _ in range(3):
            MailingDeliveryFactory(mailing=self.mailing)

        response = self.open_mailing()

        self.assertEqual(response.context["waiting_total"], 3)
        self.assertContains(response, "Waiting for the hourly limit")

    def test_tile_shows_the_next_release_time(self) -> None:
        MailingDeliveryFactory(mailing=self.mailing)
        MailingDeliveryFactory(
            mailing=MailingFactory(), released_at=timezone.now() - timedelta(minutes=5)
        )

        response = self.open_mailing()

        self.assertContains(response, "Next mail goes out at")

    def test_released_pending_deliveries_are_not_waiting(self) -> None:
        MailingDeliveryFactory(
            mailing=self.mailing, released_at=timezone.now() - timedelta(minutes=5)
        )

        response = self.open_mailing()

        self.assertEqual(response.context["waiting_total"], 0)

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_no_tile_without_the_gate(self) -> None:
        MailingDeliveryFactory(mailing=self.mailing)

        response = self.open_mailing()

        self.assertNotContains(response, "Waiting for the hourly limit")
