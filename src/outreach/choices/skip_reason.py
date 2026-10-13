from django.db import models
from django.utils.translation import gettext_lazy as _


class SkipReason(models.TextChoices):
    UNSUBSCRIBED = "unsubscribed", _("Unsubscribed")
    SUPPRESSED = "suppressed", _("Suppressed")
    COOLDOWN = "cooldown", _("Contacted recently")
    OVER_LIMIT = "over_limit", _("Over the send limit")
    NOT_MEMBER = "not_member", _("Not a member")
