from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy

from outreach.models import Audience, Prospect


class AudienceFilter(admin.SimpleListFilter):
    title = gettext_lazy("Audience")
    parameter_name = "audience"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [(str(pk), name) for pk, name in Audience.objects.values_list("pk", "name")]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[Prospect]
    ) -> QuerySet[Prospect]:
        if self.value():
            return queryset.filter(audiences=self.value())
        return queryset
