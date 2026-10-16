from typing import Any
from uuid import UUID

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, QuerySet
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
)
from django.urls import URLPattern, path, reverse
from django.utils.translation import gettext_lazy as _

from outreach.choices import DeliveryStatus, EventKind
from outreach.conf import outreach_settings
from outreach.models import Mailing
from outreach.services.mailing import ProspectMailer
from outreach.services.scheduling import MailingScheduler
from outreach.sites import outreach_site


@admin.register(Mailing, site=outreach_site)
class MailingAdmin(admin.ModelAdmin):
    list_display = [
        "subject",
        "sender",
        "created_at",
        "scheduled_for",
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

    def has_retry_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm("outreach.change_prospect")

    def get_urls(self) -> list[URLPattern]:
        return [
            path(
                "<path:object_id>/retry/",
                self.admin_site.admin_view(self.retry_view),
                name="outreach_mailing_retry",
            ),
            path(
                "<path:object_id>/cancel-schedule/",
                self.admin_site.admin_view(self.cancel_schedule_view),
                name="outreach_mailing_cancel_schedule",
            ),
            *super().get_urls(),
        ]

    def cancel_schedule_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not self.has_retry_permission(request):
            raise PermissionDenied
        mailing = self.get_object(request, object_id)
        if mailing is None:
            raise Http404
        if MailingScheduler.cancel(mailing):
            self.message_user(
                request, _("The scheduled mailing was cancelled."), messages.SUCCESS
            )
            return HttpResponseRedirect(reverse("outreach_admin:outreach_mailing_changelist"))
        self.message_user(
            request,
            _("This mailing has already started, it can not be cancelled."),
            messages.ERROR,
        )
        return HttpResponseRedirect(
            reverse("outreach_admin:outreach_mailing_change", args=[object_id])
        )

    def retry_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not self.has_retry_permission(request):
            raise PermissionDenied
        mailing = self.get_object(request, object_id)
        if mailing is None:
            raise Http404
        detail_url = reverse("outreach_admin:outreach_mailing_change", args=[mailing.pk])
        base_url = outreach_settings.base_url
        if base_url is None:
            self.message_user(
                request,
                _("OUTREACH_BASE_URL is not set, sending is disabled."),
                messages.ERROR,
            )
            return HttpResponseRedirect(detail_url)
        posted_delivery = request.POST.get("delivery")
        try:
            delivery_pk = UUID(posted_delivery) if posted_delivery else None
        except ValueError:
            raise Http404 from None
        mailer = ProspectMailer(base_url=base_url, actor=request.user.get_username())
        report = mailer.retry(mailing, delivery_pk)
        if report.queued:
            message = _("%(queued)d queued.") % {"queued": len(report.queued)}
            level = messages.SUCCESS
        else:
            message = _("%(sent)d sent, %(skipped)d skipped, %(failed)d failed.") % {
                "sent": len(report.sent),
                "skipped": len(report.skipped),
                "failed": len(report.failed),
            }
            level = messages.WARNING if report.failed else messages.SUCCESS
        self.message_user(request, message, level)
        return HttpResponseRedirect(detail_url)

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        mailing = self.get_object(request, object_id)
        recipients = []
        deliveries = []
        skipped_reasons = {}
        if mailing is not None:
            recipients = mailing.events.filter(
                kind__in=[EventKind.MAILED, EventKind.MAIL_FAILED]
            ).select_related("prospect")
            deliveries = list(
                mailing.deliveries.exclude(status=DeliveryStatus.SKIPPED).select_related(
                    "prospect"
                )
            )
            skipped_reasons = mailing.skipped_reasons
        context = {
            "recipients": recipients,
            "deliveries": deliveries,
            "can_retry": self.has_retry_permission(request),
            "failed_total": sum(
                delivery.status == DeliveryStatus.FAILED for delivery in deliveries
            ),
            "is_scheduled": any(
                delivery.status == DeliveryStatus.SCHEDULED for delivery in deliveries
            ),
            "skipped_reasons": skipped_reasons,
            **(extra_context or {}),
        }
        return super().change_view(request, object_id, form_url, context)
