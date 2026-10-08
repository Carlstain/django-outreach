import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from outreach.choices import ProspectKind, ProspectStatus


class Prospect(models.Model):
    uuid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("uuid")
    )
    email = models.EmailField(max_length=254, unique=True, verbose_name=_("email"))
    kind = models.CharField(
        max_length=20,
        choices=ProspectKind.choices,
        default=ProspectKind.INDIVIDUAL,
        verbose_name=_("kind"),
    )
    first_name = models.CharField(max_length=100, blank=True, verbose_name=_("first name"))
    last_name = models.CharField(max_length=100, blank=True, verbose_name=_("last name"))
    organization = models.CharField(max_length=160, blank=True, verbose_name=_("organization"))
    status = models.CharField(
        max_length=20,
        choices=ProspectStatus.choices,
        default=ProspectStatus.PROSPECT,
        db_index=True,
        verbose_name=_("status"),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="outreach_prospect",
        verbose_name=_("user"),
    )
    city = models.CharField(max_length=100, blank=True, verbose_name=_("city"))
    country = models.CharField(max_length=100, blank=True, verbose_name=_("country"))
    last_mailed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("last mailed at")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("prospect")
        verbose_name_plural = _("prospects")

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.organization or self.email

    @property
    def initials(self) -> str:
        name_parts = self.display_name.split()
        if self.display_name == self.email:
            return self.email[:2].upper()
        return "".join(part[0] for part in name_parts[:2]).upper()

    def save(self, *args, **kwargs) -> None:
        self.email = self.email.strip().lower()
        if self._state.adding:
            # INFO - M.E. - 07/10/26 - local import, the services import this module
            from outreach.services.linking import UserLinker
            from outreach.services.unsubscribe import SuppressionList

            if SuppressionList().contains(self.email):
                self.status = ProspectStatus.UNSUBSCRIBED
            if self.user_id is None:
                UserLinker().link(self)
        super().save(*args, **kwargs)
