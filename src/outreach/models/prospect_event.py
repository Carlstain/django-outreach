from django.db import models
from django.utils.translation import gettext_lazy as _

from outreach.choices import EventKind
from outreach.models.mailing import Mailing
from outreach.models.prospect import Prospect


class ProspectEvent(models.Model):
    """One entry in the history of a prospect: added, mailed, failed, unsubscribed, and so on."""

    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("prospect"),
    )
    mailing = models.ForeignKey(
        Mailing,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
        verbose_name=_("mailing"),
    )
    kind = models.CharField(max_length=20, choices=EventKind.choices, verbose_name=_("kind"))
    detail = models.CharField(max_length=255, blank=True, verbose_name=_("detail"))
    actor = models.CharField(max_length=150, blank=True, verbose_name=_("actor"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = _("prospect event")
        verbose_name_plural = _("prospect events")

    @classmethod
    def record(
        cls,
        prospect: Prospect,
        kind: str,
        actor: str,
        detail: str = "",
        mailing: Mailing | None = None,
    ) -> "ProspectEvent":
        """Create an event, cutting ``actor`` and ``detail`` to the size of their columns."""
        actor_max_length = cls._meta.get_field("actor").max_length
        detail_max_length = cls._meta.get_field("detail").max_length
        return cls.objects.create(
            prospect=prospect,
            kind=kind,
            actor=actor[:actor_max_length],
            detail=detail[:detail_max_length],
            mailing=mailing,
        )
