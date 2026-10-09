from django.db import models
from django.utils.translation import gettext_lazy as _


class EventKind(models.TextChoices):
    ADDED = "added", _("Added")
    IMPORTED = "imported", _("Imported")
    EDITED = "edited", _("Edited")
    LINKED = "linked", _("Linked to an account")
    MAILED = "mailed", _("Mail sent")
    MAIL_FAILED = "mail_failed", _("Mail failed")
    UNSUBSCRIBED = "unsubscribed", _("Unsubscribed")
