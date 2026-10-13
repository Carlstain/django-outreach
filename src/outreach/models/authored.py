from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from outreach.models.base import BaseModel


class AuthoredModel(BaseModel):
    """A ``BaseModel`` that records which host user created it and which changed it last.

    The users are optional and cleared when the account is deleted.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("created by"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("updated by"),
    )

    class Meta:
        abstract = True
