import uuid

from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


class EmailTemplate(models.Model):
    """A named subject and body shared by every staff member who holds the permission.

    The name is unique ignoring case. A mailing keeps its own copy, so deleting a template
    never changes history.
    """

    uuid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("uuid")
    )
    name = models.CharField(max_length=120, verbose_name=_("name"))
    subject = models.CharField(max_length=200, verbose_name=_("subject"))
    body_html = models.TextField(verbose_name=_("message"))
    created_by = models.CharField(max_length=150, blank=True, verbose_name=_("created by"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), name="outreach_emailtemplate_name_ci_unique"
            )
        ]
        verbose_name = _("email template")
        verbose_name_plural = _("email templates")

    def __str__(self) -> str:
        return self.name
