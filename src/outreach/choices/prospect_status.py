from django.db import models
from django.utils.translation import gettext_lazy as _


class ProspectStatus(models.TextChoices):
    PROSPECT = "prospect", _("Prospect")
    CONTACTED = "contacted", _("Contacted")
    UNSUBSCRIBED = "unsubscribed", _("Unsubscribed")
