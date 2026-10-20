from datetime import timedelta

from django.test import override_settings

from outreach.checks import check_send_delay, check_send_limit
from outreach.conf import outreach_settings
from tests.base import OutreachTestCase


class SendLimitChecksTests(OutreachTestCase):
    def test_unset_settings_pass(self) -> None:
        self.assertEqual(check_send_limit(None), [])
        self.assertEqual(check_send_delay(None), [])

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=0)
    def test_zero_limit_is_an_error(self) -> None:
        messages = check_send_limit(None)

        self.assertEqual([message.id for message in messages], ["outreach.E005"])

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=True)
    def test_boolean_limit_is_an_error(self) -> None:
        messages = check_send_limit(None)

        self.assertEqual([message.id for message in messages], ["outreach.E005"])

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=2.5)
    def test_float_limit_is_an_error(self) -> None:
        messages = check_send_limit(None)

        self.assertEqual([message.id for message in messages], ["outreach.E005"])

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=200)
    def test_integer_limit_passes(self) -> None:
        self.assertEqual(check_send_limit(None), [])

    @override_settings(OUTREACH_SEND_DELAY=timedelta(0))
    def test_zero_delay_is_an_error(self) -> None:
        messages = check_send_delay(None)

        self.assertEqual([message.id for message in messages], ["outreach.E006"])

    @override_settings(OUTREACH_SEND_DELAY=30)
    def test_integer_delay_is_an_error(self) -> None:
        messages = check_send_delay(None)

        self.assertEqual([message.id for message in messages], ["outreach.E006"])

    @override_settings(OUTREACH_SEND_DELAY=timedelta(seconds=2))
    def test_timedelta_delay_passes(self) -> None:
        self.assertEqual(check_send_delay(None), [])

    @override_settings(OUTREACH_DISPATCH="sync", OUTREACH_SEND_LIMIT_PER_HOUR=200)
    def test_gate_is_disabled_in_sync_mode(self) -> None:
        self.assertFalse(outreach_settings.send_gate_enabled)

    @override_settings(OUTREACH_DISPATCH="celery", OUTREACH_SEND_DELAY=timedelta(seconds=2))
    def test_gate_is_enabled_in_celery_mode_with_only_a_delay(self) -> None:
        self.assertTrue(outreach_settings.send_gate_enabled)

    @override_settings(OUTREACH_DISPATCH="celery")
    def test_gate_is_disabled_without_either_setting(self) -> None:
        self.assertFalse(outreach_settings.send_gate_enabled)
