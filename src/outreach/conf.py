from datetime import timedelta

from django.conf import settings

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
        return getattr(settings, "OUTREACH_LANGUAGE", None) or settings.LANGUAGE_CODE

    @property
    def max_recipients_per_send(self) -> int:
        return getattr(settings, "OUTREACH_MAX_RECIPIENTS_PER_SEND", 100)

    @property
    def resend_cooldown(self) -> timedelta:
        return getattr(settings, "OUTREACH_RESEND_COOLDOWN", timedelta(hours=24))

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
    def theme(self) -> OutreachTheme:
        return OutreachTheme()

    @property
    def import_header_aliases(self) -> dict[str, str]:
        return getattr(settings, "OUTREACH_IMPORT_HEADER_ALIASES", {})


outreach_settings = OutreachSettings()
