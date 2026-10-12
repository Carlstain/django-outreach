from django.apps import AppConfig
from django.core.checks import register
from django.utils.module_loading import autodiscover_modules


class OutreachConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "outreach"
    verbose_name = "Outreach"

    def ready(self) -> None:
        from outreach.checks import check_export_formulae_escaping, check_theme

        register(check_theme)
        register(check_export_formulae_escaping)
        autodiscover_modules("mail_tags")
