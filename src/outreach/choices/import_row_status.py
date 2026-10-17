from django.db import models
from django.utils.translation import gettext_lazy as _


class ImportRowStatus(models.TextChoices):
    NEW = "new", _("New")
    UPDATE = "update", _("Will update")
    SKIPPED = "skipped", _("Skipped")
    REPEATED = "repeated", _("Repeated in the file")
