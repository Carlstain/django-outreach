from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from tests.base import OutreachTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory, create_outreach_staff_user
from tests.routes import outreach_index_url


@override_settings(
    OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery", OUTREACH_SEND_LIMIT_PER_HOUR=200
)
class SendGaugeDashboardTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(["view_prospect"]))

    def release(self, count: int, minutes_ago: int = 10) -> None:
        mailing = MailingFactory()
        for _ in range(count):
            MailingDeliveryFactory(
                mailing=mailing, released_at=timezone.now() - timedelta(minutes=minutes_ago)
            )

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_no_gauge_without_a_limit(self) -> None:
        response = self.client.get(outreach_index_url())

        self.assertNotContains(response, "gauge-meter")

    def test_gauge_shows_released_over_limit(self) -> None:
        self.release(143)

        response = self.client.get(outreach_index_url())

        self.assertContains(response, "143 / 200")
        self.assertContains(response, 'max="200" value="143"')
        self.assertContains(response, "57 left this hour.")

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=3)
    def test_gauge_shows_when_a_slot_frees_while_full(self) -> None:
        self.release(3)

        response = self.client.get(outreach_index_url())

        self.assertContains(response, "3 / 3")
        self.assertContains(response, "A slot frees up at")

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_no_gauge_in_sync_mode(self) -> None:
        response = self.client.get(outreach_index_url())

        self.assertNotContains(response, "gauge-meter")
