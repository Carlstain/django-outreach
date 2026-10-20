from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib import messages
from django.contrib.admin import AdminSite
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import SimpleTemplateResponse, TemplateResponse
from django.urls import NoReverseMatch, path, reverse
from django.utils import translation
from django.utils.decorators import method_decorator
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import template_localtime
from django.utils.translation import gettext, ngettext
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache

from outreach.choices import OutreachLanguage, ProspectStatus
from outreach.conf import outreach_settings
from outreach.forms import OutreachAuthenticationForm
from outreach.models import Audience, EmailTemplate, Mailing, Prospect, ProspectEvent
from outreach.services.mail_tags import mail_tag_library
from outreach.services.mailing import MailReport, ProspectMailer
from outreach.services.prospect_csv import ProspectCsvColumns
from outreach.services.send_gate import SendGate
from outreach.services.variables import MailVariables

RECENT_EVENTS_LIMIT = 8
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
LANGUAGE_COOKIE_NAME = "outreach_language"
LANGUAGE_COOKIE_MAX_AGE = 365 * 24 * SECONDS_PER_HOUR


class OutreachAdminSite(AdminSite):
    """Second admin site, instance name ``outreach_admin``, for staff who manage outreach.

    Access needs an active staff user with ``outreach.view_prospect``. Every view runs under
    the language the staff member picked in the language menu (a cookie), or
    ``OUTREACH_LANGUAGE`` when none is set.
    """

    enable_nav_sidebar = False
    index_template = "outreach/admin/index.html"
    login_template = "outreach/admin/login.html"
    logout_template = "outreach/admin/logged_out.html"
    index_title = _("Dashboard")
    login_form = OutreachAuthenticationForm

    @property
    def site_header(self) -> str:
        return outreach_settings.site_name

    @property
    def site_title(self) -> str:
        return outreach_settings.site_name

    def has_permission(self, request: HttpRequest) -> bool:
        user = request.user
        return user.is_active and user.is_staff and user.has_perm("outreach.view_prospect")

    def mailer_for(self, request: HttpRequest) -> ProspectMailer | None:
        """Return the mailer of the logged-in staff member, or post an error and return ``None``."""
        try:
            return ProspectMailer.from_settings(request.user.get_username())
        except ImproperlyConfigured:
            messages.error(
                request, gettext("OUTREACH_BASE_URL is not set, sending is disabled.")
            )
            return None

    def report_message(self, report: MailReport) -> tuple[str, int]:
        """Return the text and the message level that tell staff what a send or retry did."""
        if report.scheduled:
            text = gettext("%(scheduled)d scheduled for %(time)s, %(skipped)d skipped.") % {
                "scheduled": len(report.scheduled),
                "time": date_format(
                    template_localtime(report.mailing.scheduled_for), "DATETIME_FORMAT"
                ),
                "skipped": len(report.skipped),
            }
            return text, messages.SUCCESS
        if report.queued:
            text = gettext("%(queued)d queued, %(skipped)d skipped.") % {
                "queued": len(report.queued),
                "skipped": len(report.skipped),
            }
            return text, messages.SUCCESS
        text = gettext("%(sent)d sent, %(skipped)d skipped, %(failed)d failed.") % {
            "sent": len(report.sent),
            "skipped": len(report.skipped),
            "failed": len(report.failed),
        }
        return text, messages.WARNING if report.failed else messages.SUCCESS

    def interface_language(self, request: HttpRequest) -> str:
        chosen = OutreachLanguage.parse(request.COOKIES.get(LANGUAGE_COOKIE_NAME))
        return chosen or outreach_settings.language

    @method_decorator(login_not_required)
    def set_language_view(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            next_url = reverse("outreach_admin:index")
        response = HttpResponseRedirect(next_url)
        chosen = OutreachLanguage.parse(request.POST.get("language"))
        if chosen:
            response.set_cookie(
                LANGUAGE_COOKIE_NAME,
                chosen,
                max_age=LANGUAGE_COOKIE_MAX_AGE,
                httponly=True,
                samesite="Lax",
                secure=request.is_secure(),
            )
        return response

    def in_outreach_language(
        self, view: Callable[..., HttpResponse]
    ) -> Callable[..., HttpResponse]:
        @wraps(view)
        def inner(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            with translation.override(self.interface_language(request)):
                response = view(request, *args, **kwargs)
                # INFO - M.E. - 07/10/26 - a TemplateResponse renders after the view
                # returns, so it is rendered here while the language is still active
                if isinstance(response, SimpleTemplateResponse):
                    response.render()
            return response

        return inner

    def admin_view(
        self, view: Callable[..., HttpResponse], cacheable: bool = False
    ) -> Callable[..., HttpResponse]:
        return self.in_outreach_language(super().admin_view(view, cacheable))

    @method_decorator(never_cache)
    @login_not_required
    def login(self, request: HttpRequest, extra_context: dict | None = None) -> HttpResponse:
        return self.in_outreach_language(super().login)(request, extra_context)

    def each_context(self, request: HttpRequest) -> dict[str, Any]:
        return {
            **super().each_context(request),
            "site_name": outreach_settings.site_name,
            "logo_path": outreach_settings.logo_static_path,
            "logo_dark_path": outreach_settings.logo_dark_static_path,
            "django_admin_url": self.django_admin_url(),
            "theme": outreach_settings.theme,
            "counts": self.prospect_counts(),
            "languages": OutreachLanguage.choices,
            "interface_language": translation.get_language(),
        }

    def django_admin_url(self) -> str | None:
        try:
            default_admin_url = reverse("admin:index", current_app="admin")
        except NoReverseMatch:
            return None
        if default_admin_url == reverse("outreach_admin:index"):
            return None
        return default_admin_url

    def prospect_counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in ProspectStatus}
        status_totals = Prospect.objects.values("status").annotate(total=Count("pk"))
        for status_total in status_totals:
            counts[status_total["status"]] = status_total["total"]
        counts["total"] = sum(counts.values())
        counts["members"] = Prospect.objects.filter(user__isnull=False).count()
        counts["mailings"] = Mailing.objects.count()
        counts["email_templates"] = EmailTemplate.objects.count()
        counts["audiences"] = Audience.objects.count()
        return counts

    def get_urls(self) -> list:
        return [
            path("help/", self.admin_view(self.help_view), name="help"),
            path("language/", never_cache(self.set_language_view), name="set_language"),
            *super().get_urls(),
        ]

    def cooldown_label(self) -> str:
        seconds = int(outreach_settings.resend_cooldown.total_seconds())
        if seconds and seconds % SECONDS_PER_HOUR == 0:
            hours = seconds // SECONDS_PER_HOUR
            return ngettext("%(count)d hour", "%(count)d hours", hours) % {"count": hours}
        if seconds and seconds % SECONDS_PER_MINUTE == 0:
            minutes = seconds // SECONDS_PER_MINUTE
            return ngettext("%(count)d minute", "%(count)d minutes", minutes) % {
                "count": minutes
            }
        return ngettext("%(count)d second", "%(count)d seconds", seconds) % {"count": seconds}

    def help_view(self, request: HttpRequest) -> TemplateResponse:
        context = {
            **self.each_context(request),
            "title": _("How to use"),
            "variables": MailVariables().catalog(),
            "mail_tags": mail_tag_library.catalog(),
            "max_recipients": outreach_settings.recipient_cap,
            "cooldown_label": self.cooldown_label(),
            "import_columns": ProspectCsvColumns().with_aliases(),
        }
        return TemplateResponse(request, "outreach/admin/help.html", context)

    def index(self, request: HttpRequest, extra_context: dict | None = None) -> HttpResponse:
        recent_events = ProspectEvent.objects.select_related("prospect")[:RECENT_EVENTS_LIMIT]
        context = {
            "recent_events": recent_events,
            "max_recipients": outreach_settings.recipient_cap,
            "cooldown_label": self.cooldown_label(),
            "send_usage": SendGate.usage(),
            **(extra_context or {}),
        }
        return super().index(request, context)


outreach_site = OutreachAdminSite(name="outreach_admin")
