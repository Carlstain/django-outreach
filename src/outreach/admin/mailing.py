from typing import Any

from django.contrib import admin
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _

from outreach.choices import DeliveryStatus, EventKind
from outreach.models import Mailing
from outreach.sites import outreach_site


@admin.register(Mailing, site=outreach_site)
class MailingAdmin(admin.ModelAdmin):
    list_display = [
        "subject",
        "sender",
        "created_at",
        "pending_count",
        "sent_count",
        "failed_count",
        "skipped_count",
    ]
    ordering = ["-created_at"]
    search_fields = ["subject", "sender"]
    change_list_template = "outreach/admin/mailing_list.html"
    change_form_template = "outreach/admin/mailing_detail.html"
    delete_selected_confirmation_template = "outreach/admin/delete_selected_confirmation.html"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Mailing]:
        return (
            super()
            .get_queryset(request)
            .annotate(
                pending=Count(
                    "deliveries", filter=Q(deliveries__status=DeliveryStatus.PENDING)
                )
            )
        )

    @admin.display(description=_("pending"), ordering="pending")
    def pending_count(self, mailing: Mailing) -> int:
        return mailing.pending

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Mailing | None = None) -> bool:
        return False

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        mailing = self.get_object(request, object_id)
        recipients = []
        skipped_reasons = {}
        if mailing is not None:
            recipients = mailing.events.filter(
                kind__in=[EventKind.MAILED, EventKind.MAIL_FAILED]
            ).select_related("prospect")
            skipped_reasons = mailing.skipped_reasons
        context = {
            "recipients": recipients,
            "skipped_reasons": skipped_reasons,
            **(extra_context or {}),
        }
        return super().change_view(request, object_id, form_url, context)
