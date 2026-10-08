from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning

from outreach.theme import OutreachTheme


def check_theme(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    return [Error(message, id="outreach.E001") for message in OutreachTheme().errors()]


def check_export_formulae_escaping(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    if getattr(settings, "IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT", False) is True:
        return []
    return [
        Warning(
            "Prospect exports can contain spreadsheet formulas typed by users: "
            "set IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT = True.",
            hint="Add IMPORT_EXPORT_ESCAPE_FORMULAE_ON_EXPORT = True to your settings.",
            id="outreach.W001",
        )
    ]
