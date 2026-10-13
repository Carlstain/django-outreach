from typing import Any

from django.contrib import admin
from django.db import IntegrityError
from django.forms import ModelForm
from django.http import HttpRequest, HttpResponse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from outreach.conf import outreach_settings
from outreach.forms import (
    EmailTemplateForm,
)
from outreach.models import EmailTemplate
from outreach.services.body import MailBodySanitizer
from outreach.services.mail_buttons import mail_buttons
from outreach.services.mail_tags import mail_tag_library
from outreach.services.variables import MailVariables
from outreach.sites import outreach_site


@admin.register(EmailTemplate, site=outreach_site)
class EmailTemplateAdmin(admin.ModelAdmin):
    form = EmailTemplateForm
    list_display = ["name", "subject", "kind_badge", "updated_at", "created_by"]
    search_fields = ["name", "subject"]
    ordering = ["name"]
    list_per_page = 20
    change_list_template = "outreach/admin/emailtemplate_list.html"
    change_form_template = "outreach/admin/emailtemplate_form.html"
    delete_selected_confirmation_template = "outreach/admin/delete_selected_confirmation.html"

    @admin.display(description=gettext_lazy("Type"), ordering="is_newsletter")
    def kind_badge(self, template: EmailTemplate) -> str:
        if template.is_newsletter:
            return format_html('<span class="badge contacted">{}</span>', _("Newsletter"))
        return format_html('<span class="badge user">{}</span>', _("Notice"))

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
            # INFO - M.E. - 08/10/26 - a concurrent save took the name after the form check;
            # the failed attempt is rolled back, so the second pass reports it as a form error
            return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(
        self, request: HttpRequest, obj: EmailTemplate, form: ModelForm, change: bool
    ) -> None:
        if not change:
            created_by_max_length = EmailTemplate._meta.get_field("created_by").max_length
            obj.created_by = request.user.get_username()[:created_by_max_length]
        super().save_model(request, obj, form, change)

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: EmailTemplate | None = None,
    ) -> HttpResponse:
        if obj is not None:
            variables = MailVariables()
            sample_values = {
                variable.key: str(variable.example) for variable in variables.catalog()
            }
            sample_values["unsubscribe_url"] = "https://example.org/unsubscribe/sample/"
            sanitizer = MailBodySanitizer()
            body_with_tokens, buttons = mail_buttons.extract(
                sanitizer.clean(obj.body_html),
                lambda argument: mail_tag_library.resolve_example(argument, sample_values),
                strict=False,
            )
            tagged_html = mail_tag_library.render_examples(body_with_tokens, html=True)
            personalised_html = variables.render(tagged_html, sample_values, html=True)
            context["sample_preview_html"] = mail_buttons.insert(
                sanitizer.clean(personalised_html), buttons, outreach_settings.theme.email
            )
            tagged_subject = mail_tag_library.render_examples(obj.subject, html=False)
            context["sample_preview_subject"] = variables.render(
                tagged_subject, sample_values, html=False
            )
        return super().render_change_form(request, context, add, change, form_url, obj)
