from typing import Any

from django.contrib import admin
from django.db import IntegrityError
from django.db.models import Count, QuerySet
from django.forms import ModelForm
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy

from outreach.forms import AudienceForm
from outreach.models import Audience
from outreach.sites import outreach_site


@admin.register(Audience, site=outreach_site)
class AudienceAdmin(admin.ModelAdmin):
    form = AudienceForm
    list_display = ["name", "description", "member_count", "updated_at", "created_by"]
    list_select_related = ["created_by"]
    search_fields = ["name", "description"]
    ordering = ["name"]
    list_per_page = 20
    change_list_template = "outreach/admin/audience_list.html"
    change_form_template = "outreach/admin/audience_form.html"
    delete_selected_confirmation_template = "outreach/admin/delete_selected_confirmation.html"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Audience]:
        return super().get_queryset(request).annotate(members=Count("prospects"))

    @admin.display(description=gettext_lazy("Prospects"), ordering="members")
    def member_count(self, audience: Audience) -> int:
        return audience.members

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except IntegrityError:
            # INFO - M.E. - 13/10/26 - a concurrent save took the name after the form check;
            # the failed attempt is rolled back, so the second pass reports it as a form error
            return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(
        self, request: HttpRequest, obj: Audience, form: ModelForm, change: bool
    ) -> None:
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
