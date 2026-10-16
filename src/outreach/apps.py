from django.apps import AppConfig
from django.core.checks import Tags, register
from django.utils.module_loading import autodiscover_modules


class OutreachConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "outreach"
    verbose_name = "Outreach"

    def ready(self) -> None:
        from outreach.checks import (
            check_dispatch,
            check_sync_dispatch_in_production,
            check_theme,
        )

        register(check_theme)
        register(check_dispatch)
        register(check_sync_dispatch_in_production, Tags.security, deploy=True)
        autodiscover_modules("mail_tags")
        autodiscover_modules("mail_variables")
