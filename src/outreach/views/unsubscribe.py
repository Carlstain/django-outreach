from django.contrib.auth.decorators import login_not_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import translation
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from outreach.choices import ACTOR_RECIPIENT
from outreach.conf import outreach_settings
from outreach.models import Prospect
from outreach.services.unsubscribe import ProspectUnsubscriber, UnsubscribeTokens


@method_decorator([csrf_exempt, never_cache, login_not_required], name="dispatch")
class UnsubscribeView(View):
    http_method_names = ["get", "post", "head", "options"]

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        with translation.override(outreach_settings.language):
            response = super().dispatch(request, *args, **kwargs)
        response["Referrer-Policy"] = "no-referrer"
        return response

    def page_context(self, email: str) -> dict[str, str | None]:
        return {
            "masked_email": self.mask_email(email) if email else "",
            "site_name": outreach_settings.site_name,
            "logo_path": outreach_settings.logo_static_path,
            "logo_dark_path": outreach_settings.logo_dark_static_path,
        }

    def mask_email(self, email: str) -> str:
        local_part, _separator, domain = email.partition("@")
        return f"{local_part[:1]}{'•' * len(local_part[1:])}@{domain}"

    def get(self, request: HttpRequest, token: str) -> HttpResponse:
        try:
            prospect = UnsubscribeTokens().resolve(token)
        except Prospect.DoesNotExist as error:
            if UnsubscribeTokens().is_signed(token):
                return render(request, "outreach/unsubscribed.html", self.page_context(""))
            raise Http404 from error
        context = self.page_context(prospect.email)
        return render(request, "outreach/unsubscribe.html", context)

    def post(self, request: HttpRequest, token: str) -> HttpResponse:
        tokens = UnsubscribeTokens()
        try:
            prospect = tokens.resolve(token)
        except Prospect.DoesNotExist as error:
            if tokens.is_signed(token):
                return render(request, "outreach/unsubscribed.html", self.page_context(""))
            raise Http404 from error
        ProspectUnsubscriber().unsubscribe(prospect, ACTOR_RECIPIENT)
        context = self.page_context(prospect.email)
        return render(request, "outreach/unsubscribed.html", context)
