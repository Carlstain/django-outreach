from importlib.util import find_spec
from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, Warning

from outreach.choices import DispatchMode, OutreachLanguage
from outreach.conf import outreach_settings
from outreach.theme import OutreachTheme


def check_theme(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    return [Error(message, id="outreach.E001") for message in OutreachTheme().errors()]


def check_dispatch(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    dispatch = outreach_settings.dispatch
    if dispatch not in DispatchMode.values:
        choices = ", ".join(DispatchMode.values)
        return [Error(f"OUTREACH_DISPATCH must be one of: {choices}.", id="outreach.E002")]
    if dispatch == DispatchMode.CELERY and find_spec("celery") is None:
        return [
            Error(
                'OUTREACH_DISPATCH is "celery" but Celery is not installed.',
                hint="Install it with: pip install django-outreach[celery]",
                id="outreach.E003",
            )
        ]
    return []


def check_mail_language(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    configured = outreach_settings.configured_mail_language
    if configured and OutreachLanguage.parse(configured) is None:
        choices = ", ".join(OutreachLanguage.values)
        return [
            Error(f"OUTREACH_MAIL_LANGUAGE must be one of: {choices}.", id="outreach.E004")
        ]
    return []


def check_sync_dispatch_in_production(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    if outreach_settings.dispatch == DispatchMode.SYNC and not settings.DEBUG:
        return [
            Warning(
                "Mail is sent synchronously inside the admin request.",
                hint='Set OUTREACH_DISPATCH = "celery" for production.',
                id="outreach.W001",
            )
        ]
    return []
