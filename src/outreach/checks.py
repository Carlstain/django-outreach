from typing import Any

from django.core.checks import CheckMessage, Error

from outreach.theme import OutreachTheme


def check_theme(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    return [Error(message, id="outreach.E001") for message in OutreachTheme().errors()]
