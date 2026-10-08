from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy

from outreach.models import Prospect


class MemberFilter(admin.SimpleListFilter):
    title = gettext_lazy("Member")
    parameter_name = "member"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [("yes", gettext_lazy("Yes")), ("no", gettext_lazy("No"))]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[Prospect]
    ) -> QuerySet[Prospect]:
        if self.value() == "yes":
            return queryset.filter(user__isnull=False)
        if self.value() == "no":
            return queryset.filter(user__isnull=True)
        return queryset
