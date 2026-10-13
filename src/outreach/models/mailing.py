import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class Mailing(models.Model):
    """One send action that had at least one recipient.

    It keeps a copy of the subject and body and counts of the skipped recipients, never their
    names.
    """

    uuid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("uuid")
    )
    subject = models.CharField(max_length=200, verbose_name=_("subject"))
    body_html = models.TextField(verbose_name=_("message"))
    sender = models.CharField(max_length=150, verbose_name=_("sender"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    sent_count = models.PositiveIntegerField(default=0, verbose_name=_("sent"))
    failed_count = models.PositiveIntegerField(default=0, verbose_name=_("failed"))
    skipped_count = models.PositiveIntegerField(default=0, verbose_name=_("skipped"))
    skipped_reasons = models.JSONField(default=dict, verbose_name=_("skipped reasons"))

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("mailing")
        verbose_name_plural = _("mailings")

    def __str__(self) -> str:
        return self.subject
