from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from outreach.models.authored import AuthoredModel


class Audience(AuthoredModel):
    """A named, static set of prospects that staff mail again and again.

    The name is unique ignoring case. Membership never overrides an unsubscription: a member
    who unsubscribed is skipped when the audience is mailed, like any other prospect.
    """

    name = models.CharField(max_length=120, verbose_name=_("name"))
    description = models.CharField(max_length=255, blank=True, verbose_name=_("description"))

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="outreach_audience_name_ci_unique")
        ]
        verbose_name = _("audience")
        verbose_name_plural = _("audiences")

    def __str__(self) -> str:
        return self.name
