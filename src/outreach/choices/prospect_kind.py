from django.db import models
from django.utils.translation import gettext_lazy as _


class ProspectKind(models.TextChoices):
    INDIVIDUAL = "individual", _("Individual")
    ORGANIZATION = "organization", _("Organization")
