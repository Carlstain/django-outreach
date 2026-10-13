from collections.abc import Iterable

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
        return cls.objects.create(
            prospect=prospect, kind=kind, mailing=mailing, **cls.fit_to_columns(actor, detail)
        )

    @classmethod
    def record_many(
        cls, prospect_pks: Iterable[object], kind: str, actor: str, detail: str = ""
    ) -> None:
        """Create the same event for each prospect in one insert."""
        fitted = cls.fit_to_columns(actor, detail)
        cls.objects.bulk_create(
            cls(prospect_id=prospect_pk, kind=kind, **fitted) for prospect_pk in prospect_pks
        )

    @classmethod
    def fit_to_columns(cls, actor: str, detail: str) -> dict[str, str]:
        return {
            "actor": actor[: cls._meta.get_field("actor").max_length],
            "detail": detail[: cls._meta.get_field("detail").max_length],
        }
