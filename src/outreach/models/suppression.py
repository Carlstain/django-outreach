from django.db import models
from django.utils.translation import gettext_lazy as _


class Suppression(models.Model):
    """A hashed address that must never be mailed. It outlives the prospect."""

    email_hash = models.CharField(
        max_length=64, primary_key=True, verbose_name=_("email hash")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))

    class Meta:
        verbose_name = _("suppression")
        verbose_name_plural = _("suppressions")
