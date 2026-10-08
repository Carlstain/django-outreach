from django.conf import settings
from django.core.checks import Warning as CheckWarning
from django.core.checks import run_checks
from django.test import override_settings

from tests.base import OutreachTestCase

EXPECTED_WARNING = CheckWarning(
    "Prospect exports can contain spreadsheet formulas typed by users: "
    "set IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT = True.",
    hint="Add IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT = True to your settings.",
    id="outreach.W001",
)


def formula_warnings() -> list[CheckWarning]:
    return [message for message in run_checks() if message.id == "outreach.W001"]


class ExportFormulaCheckTests(OutreachTestCase):
    @override_settings(IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT=True)
    def test_no_warning_when_formulas_are_escaped(self) -> None:
        self.assertEqual(formula_warnings(), [])

    @override_settings(IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT=False)
    def test_warning_when_escaping_is_disabled(self) -> None:
        self.assertEqual(formula_warnings(), [EXPECTED_WARNING])

    @override_settings(IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT="yes")
    def test_warning_when_the_setting_is_not_exactly_true(self) -> None:
        self.assertEqual(formula_warnings(), [EXPECTED_WARNING])

    def test_warning_when_the_setting_is_missing(self) -> None:
        with override_settings():
            del settings.IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT

            self.assertEqual(formula_warnings(), [EXPECTED_WARNING])
