from django.db import models
from django.utils.translation import gettext_lazy as _


class DispatchMode(models.TextChoices):
    SYNC = "sync", _("Synchronous")
    CELERY = "celery", _("Celery")
