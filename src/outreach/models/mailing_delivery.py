import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from outreach.choices import DeliveryStatus
from outreach.models.mailing import Mailing
from outreach.models.prospect import Prospect


class MailingDelivery(models.Model):
    """One recipient of a mailing, from the moment it is claimed until it is sent or failed.

    It holds the ``last_mailed_at`` the claim replaced, so a failure can restore it.
    """

    uuid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, verbose_name=_("uuid")
    )
    mailing = models.ForeignKey(
        Mailing,
        on_delete=models.CASCADE,
        related_name="deliveries",
        verbose_name=_("mailing"),
    )
    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        related_name="deliveries",
        verbose_name=_("prospect"),
    )
    status = models.CharField(
        max_length=10,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        verbose_name=_("status"),
    )
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name=_("attempts"))
    previous_mailed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("previous mailed at")
    )
    last_error = models.CharField(max_length=255, blank=True, verbose_name=_("last error"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = _("mailing delivery")
        verbose_name_plural = _("mailing deliveries")
        indexes = [
            models.Index(fields=["mailing", "status"], name="outreach_dlv_mailing_status"),
            models.Index(fields=["status", "updated_at"], name="outreach_dlv_status_age"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["mailing", "prospect"], name="outreach_delivery_unique_recipient"
            )
        ]

    def __str__(self) -> str:
        return f"{self.mailing_id} / {self.prospect_id}"
