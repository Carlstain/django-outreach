from django.db import models
from django.utils.translation import gettext_lazy as _


class SyncUsersMode(models.TextChoices):
    LINK = "link", _("Link only")
    CREATE = "create", _("Create and link")
