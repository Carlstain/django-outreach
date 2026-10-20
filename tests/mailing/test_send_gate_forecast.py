from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.services.send_gate import SendGate
from tests.base import OutreachTestCase
from tests.factories import MailingDeliveryFactory, MailingFactory


@override_settings(OUTREACH_DISPATCH="celery", OUTREACH_SEND_LIMIT_PER_HOUR=200)
class SendGateForecastTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.now = timezone.now()
        mailing = MailingFactory()
        for _ in range(143):
            MailingDeliveryFactory(
                mailing=mailing, released_at=self.now - timedelta(minutes=10)
            )

    def test_all_go_now_under_the_budget(self) -> None:
        forecast = SendGate.forecast(10, self.now)

        self.assertEqual(forecast.go_now, 10)
        self.assertEqual(forecast.waiting, 0)
        self.assertIsNone(forecast.finishes_in)

    def test_surplus_waits(self) -> None:
        forecast = SendGate.forecast(480, self.now)

        self.assertEqual(forecast.go_now, 57)
        self.assertEqual(forecast.waiting, 423)

    def test_finishes_in_rounds_up_to_whole_hours_with_a_limit(self) -> None:
        forecast = SendGate.forecast(480, self.now)

        self.assertEqual(forecast.finishes_in, timedelta(hours=3))

    @override_settings(
        OUTREACH_SEND_LIMIT_PER_HOUR=None, OUTREACH_SEND_DELAY=timedelta(seconds=30)
    )
    def test_finishes_in_follows_the_delay_without_a_limit(self) -> None:
        forecast = SendGate.forecast(10, self.now)

        self.assertEqual(forecast.go_now, 1)
        self.assertEqual(forecast.waiting, 9)
        self.assertEqual(forecast.finishes_in, timedelta(seconds=270))

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_everything_goes_now_without_the_gate(self) -> None:
        forecast = SendGate.forecast(480, self.now)

        self.assertEqual(forecast.go_now, 480)
        self.assertEqual(forecast.waiting, 0)

    def test_waiting_deliveries_of_other_mailings_go_first(self) -> None:
        backlog_mailing = MailingFactory()
        for _ in range(100):
            MailingDeliveryFactory(mailing=backlog_mailing)

        forecast = SendGate.forecast(10, self.now)

        self.assertEqual(forecast.go_now, 0)
        self.assertEqual(forecast.waiting, 10)
        self.assertEqual(forecast.finishes_in, timedelta(hours=1))
