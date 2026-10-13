from unittest.mock import patch

from django.test import override_settings

from outreach.checks import check_dispatch, check_sync_dispatch_in_production
from tests.base import OutreachTestCase


class DispatchChecksTests(OutreachTestCase):
    @override_settings(OUTREACH_DISPATCH="threads")
    def test_an_unknown_dispatch_mode_is_an_error(self) -> None:
        messages = check_dispatch(None)

        self.assertEqual([message.id for message in messages], ["outreach.E002"])

    @override_settings(OUTREACH_DISPATCH="celery")
    def test_celery_mode_without_celery_installed_is_an_error(self) -> None:
        with patch("outreach.checks.find_spec", return_value=None):
            messages = check_dispatch(None)

        self.assertEqual([message.id for message in messages], ["outreach.E003"])

    @override_settings(OUTREACH_DISPATCH="celery")
    def test_celery_mode_with_celery_installed_is_clean(self) -> None:
        self.assertEqual(check_dispatch(None), [])

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_sync_mode_is_valid(self) -> None:
        self.assertEqual(check_dispatch(None), [])

    @override_settings(OUTREACH_DISPATCH="sync", DEBUG=False)
    def test_sync_mode_in_production_is_a_warning(self) -> None:
        messages = check_sync_dispatch_in_production(None)

        self.assertEqual([message.id for message in messages], ["outreach.W001"])

    @override_settings(OUTREACH_DISPATCH="sync", DEBUG=True)
    def test_sync_mode_while_debugging_is_not_reported(self) -> None:
        self.assertEqual(check_sync_dispatch_in_production(None), [])

    @override_settings(OUTREACH_DISPATCH="celery", DEBUG=False)
    def test_celery_mode_in_production_is_not_reported(self) -> None:
        self.assertEqual(check_sync_dispatch_in_production(None), [])
