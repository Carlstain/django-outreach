from django.db import models
from django.utils.translation import gettext_lazy as _


class FailureKind(models.TextChoices):
    REFUSED = "refused", _("The mail server refused it")
    SERVER = "server", _("The mail server could not be reached")
    CONTENT = "content", _("The message could not be built")
