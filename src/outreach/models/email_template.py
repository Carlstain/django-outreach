from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from outreach.choices import OutreachLanguage
from outreach.models.authored import AuthoredModel


class EmailTemplate(AuthoredModel):
    """A named subject and body shared by every staff member who holds the permission.

    The name is unique ignoring case. A mailing keeps its own copy, so deleting a template
    never changes history.
    """

    name = models.CharField(max_length=120, verbose_name=_("name"))
    subject = models.CharField(max_length=200, verbose_name=_("subject"))
    body_html = models.TextField(verbose_name=_("message"))
    header_text = models.CharField(max_length=120, blank=True, verbose_name=_("header text"))
    is_newsletter = models.BooleanField(default=True, verbose_name=_("newsletter"))
    language = models.CharField(
        max_length=7,
        blank=True,
        choices=[("", _("Mail default")), *OutreachLanguage.choices],
        verbose_name=_("language"),
    )

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
