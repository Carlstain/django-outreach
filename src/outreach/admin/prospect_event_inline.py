from django.contrib import admin
from django.http import HttpRequest

from outreach.models import Prospect, ProspectEvent


class ProspectEventInline(admin.TabularInline):
    model = ProspectEvent
    fields = ["created_at", "kind", "detail", "actor"]
    readonly_fields = ["created_at", "kind", "detail", "actor"]
    ordering = ["-created_at", "-pk"]
    extra = 0

    def has_add_permission(self, request: HttpRequest, obj: Prospect | None = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Prospect | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Prospect | None = None) -> bool:
        return False
