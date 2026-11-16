from django.apps import AppConfig
from django.contrib.auth import get_user_model
from django.core.checks import Tags, register
from django.db.models.signals import post_save
from django.utils.module_loading import autodiscover_modules


class OutreachConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "outreach"
    verbose_name = "Outreach"

    def ready(self) -> None:
        from outreach.checks import (
            check_dispatch,
            check_mail_language,
            check_send_delay,
            check_send_limit,
            check_sync_dispatch_in_production,
            check_sync_users,
            check_theme,
        )

        register(check_theme)
        register(check_dispatch)
        register(check_mail_language)
        register(check_send_limit)
        register(check_send_delay)
        register(check_sync_users)
        register(check_sync_dispatch_in_production, Tags.security, deploy=True)
        from outreach.receivers import sync_new_user

        post_save.connect(
            sync_new_user, sender=get_user_model(), dispatch_uid="outreach_sync_new_user"
        )
        autodiscover_modules("mail_tags")
        autodiscover_modules("mail_variables")
