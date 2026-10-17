from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.templatetags.static import static
from django.utils.module_loading import import_string

from outreach.choices import DispatchMode, OutreachLanguage
from outreach.theme import OutreachTheme


class OutreachSettings:
    @property
    def site_name(self) -> str:
        return getattr(settings, "OUTREACH_SITE_NAME", "Outreach")

    @property
    def base_url(self) -> str | None:
        return getattr(settings, "OUTREACH_BASE_URL", None) or None

    @property
    def from_email(self) -> str:
        return getattr(settings, "OUTREACH_FROM_EMAIL", None) or settings.DEFAULT_FROM_EMAIL

    @property
    def language(self) -> str:
        configured = getattr(settings, "OUTREACH_LANGUAGE", None) or settings.LANGUAGE_CODE
        return OutreachLanguage.parse(configured) or configured

    @property
    def configured_mail_language(self) -> str | None:
        return getattr(settings, "OUTREACH_MAIL_LANGUAGE", None) or None

    @property
    def mail_language(self) -> str:
        return (
            OutreachLanguage.parse(self.configured_mail_language)
            or OutreachLanguage.parse(self.language)
            or OutreachLanguage.EN.value
        )

    @property
    def max_recipients_per_send(self) -> int:
        return getattr(settings, "OUTREACH_MAX_RECIPIENTS_PER_SEND", 100)

    @property
    def dispatch(self) -> str:
        return getattr(settings, "OUTREACH_DISPATCH", DispatchMode.SYNC)

    @property
    def celery_max_recipients_per_send(self) -> int:
        return getattr(settings, "OUTREACH_CELERY_MAX_RECIPIENTS_PER_SEND", 5000)

    @property
    def uses_celery(self) -> bool:
        return self.dispatch == DispatchMode.CELERY

    @property
    def recipient_cap(self) -> int:
        if self.dispatch == DispatchMode.CELERY:
            return self.celery_max_recipients_per_send
        return self.max_recipients_per_send

    @property
    def celery_queue(self) -> str | None:
        return getattr(settings, "OUTREACH_CELERY_QUEUE", None)

    @property
    def delivery_max_retries(self) -> int:
        return getattr(settings, "OUTREACH_DELIVERY_MAX_RETRIES", 3)

    @property
    def resend_cooldown(self) -> timedelta:
        return getattr(settings, "OUTREACH_RESEND_COOLDOWN", timedelta(seconds=10))

    @property
    def max_import_rows(self) -> int:
        return getattr(settings, "OUTREACH_MAX_IMPORT_ROWS", 5000)

    @property
    def max_import_bytes(self) -> int:
        return getattr(settings, "OUTREACH_MAX_IMPORT_BYTES", 2_000_000)

    @property
    def logo_static_path(self) -> str | None:
        return getattr(settings, "OUTREACH_LOGO_STATIC_PATH", None)

    @property
    def logo_dark_static_path(self) -> str | None:
        return getattr(settings, "OUTREACH_LOGO_DARK_STATIC_PATH", None)

    @property
    def email_logo_in_header(self) -> bool:
        return getattr(settings, "OUTREACH_EMAIL_LOGO_IN_HEADER", False)

    @property
    def email_logo_in_footer(self) -> bool:
        return getattr(settings, "OUTREACH_EMAIL_LOGO_IN_FOOTER", False)

    @property
    def email_logo_url(self) -> str | None:
        if not self.logo_static_path:
            return None
        logo_url = static(self.logo_static_path)
        if logo_url.startswith(("http://", "https://")) or not self.base_url:
            return logo_url
        return f"{self.base_url.rstrip('/')}{logo_url}"

    @property
    def theme(self) -> OutreachTheme:
        return OutreachTheme()

    @property
    def import_header_aliases(self) -> dict[str, str]:
        return getattr(settings, "OUTREACH_IMPORT_HEADER_ALIASES", {})

    @property
    def user_prospect_fields(self) -> Callable[[Any], dict[str, Any]] | None:
        dotted_path = getattr(settings, "OUTREACH_USER_PROSPECT_FIELDS", None)
        return import_string(dotted_path) if dotted_path else None


outreach_settings = OutreachSettings()
