from typing import Any

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext
from import_export.admin import ImportExportModelAdmin

from outreach.admin.member_filter import MemberFilter
from outreach.admin.prospect_event_inline import ProspectEventInline
from outreach.choices import ACTOR_SYSTEM, EventKind, ProspectKind, ProspectStatus
from outreach.conf import outreach_settings
from outreach.forms import (
    MessageForm,
    OutreachExportForm,
    OutreachImportForm,
    ProspectForm,
    SaveTemplateForm,
)
from outreach.models import EmailTemplate, Prospect, ProspectEvent
from outreach.resources import ProspectResource
from outreach.services.linking import UserLinker
from outreach.services.mail_buttons import InvalidButtonLink
from outreach.services.mailing import ProspectMailer
from outreach.services.templates import EmailTemplates, TemplateNameTaken
from outreach.services.unsubscribe import ProspectUnsubscriber
from outreach.sites import outreach_site

STEP_PREVIEW = "preview"
STEP_SEND = "send"
STEP_COMPOSE = "compose"
STEP_SAVE_TEMPLATE = "save_template"
FALSE_VALUES = ("", "0", "false")
STATUS_BADGE_CLASSES = {
    ProspectStatus.PROSPECT: "prospect",
    ProspectStatus.CONTACTED: "contacted",
    ProspectStatus.UNSUBSCRIBED: "unsub",
}


@admin.register(Prospect, site=outreach_site)
class ProspectAdmin(ImportExportModelAdmin):
    form = ProspectForm
    import_form_class = OutreachImportForm
    export_form_class = OutreachExportForm
    resource_classes = [ProspectResource]
    list_per_page = 20
    list_display = ["display_name", "email", "status_badge", "member", "last_mailed_at"]
    list_filter = ["kind", "status", MemberFilter]
    search_fields = ["email", "first_name", "last_name", "organization"]
    inlines = [ProspectEventInline]
    actions = ["send_mail", "unsubscribe_selected", "link_users"]
    change_list_template = "outreach/admin/change_list.html"
    change_form_template = "outreach/admin/change_form.html"
    delete_confirmation_template = "outreach/admin/delete_confirmation.html"
    delete_selected_confirmation_template = "outreach/admin/delete_selected_confirmation.html"
    import_template_name = "outreach/admin/import.html"
    export_template_name = "outreach/admin/export.html"

    @admin.display(description=gettext_lazy("Name"), ordering="first_name")
    def display_name(self, prospect: Prospect) -> str:
        name = prospect.display_name
        avatar_class = f"outreach-avatar tone-{prospect.avatar_tone}"
        if prospect.kind == ProspectKind.ORGANIZATION:
            avatar_class += " org"
        return format_html(
            '<span class="{}" aria-hidden="true">{}</span>'
            '<span class="outreach-name">{}<small class="outreach-sub">{}</small></span>',
            avatar_class,
            prospect.initials,
            name,
            prospect.get_kind_display(),
        )

    @admin.display(description=gettext_lazy("Status"), ordering="status")
    def status_badge(self, prospect: Prospect) -> str:
        badge_class = STATUS_BADGE_CLASSES[prospect.status]
        return format_html(
            '<span class="badge {}">{}</span>', badge_class, prospect.get_status_display()
        )

    @admin.display(description=gettext_lazy("Member"), ordering="user")
    def member(self, prospect: Prospect) -> str:
        if prospect.user_id is None:
            return ""
        return format_html('<span class="badge user">{}</span>', _("Member"))

    def get_fields(self, request: HttpRequest, obj: Prospect | None = None) -> list[str]:
        editable_fields = [
            "email",
            "kind",
            "first_name",
            "last_name",
            "organization",
            "city",
            "country",
        ]
        if obj is None:
            return editable_fields
        return editable_fields + [
            "status",
            "last_mailed_at",
            "user",
            "created_at",
            "updated_at",
        ]

    def get_readonly_fields(
        self, request: HttpRequest, obj: Prospect | None = None
    ) -> list[str]:
        readonly_fields = ["status", "last_mailed_at", "user", "created_at", "updated_at"]
        if obj is not None:
            readonly_fields.append("email")
        return readonly_fields

    def has_import_permission(self, request: HttpRequest) -> bool:
        return self.has_add_permission(request)

    def has_export_permission(self, request: HttpRequest) -> bool:
        return self.has_view_permission(request)

    def get_import_data_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        import_kwargs = super().get_import_data_kwargs(**kwargs)
        import_kwargs["rollback_on_validation_errors"] = True
        return import_kwargs

    def save_model(
        self, request: HttpRequest, obj: Prospect, form: ModelForm, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)
        kind = EventKind.EDITED if change else EventKind.ADDED
        detail = ", ".join(form.changed_data) if change else ""
        ProspectEvent.record(obj, kind, request.user.get_username(), detail=detail)

    @admin.action(
        description=gettext_lazy("Send a mail to the selected prospects"),
        permissions=["change"],
    )
    def send_mail(
        self, request: HttpRequest, queryset: QuerySet[Prospect]
    ) -> HttpResponse | None:
        base_url = outreach_settings.base_url
        if base_url is None:
            self.message_user(
                request,
                _("OUTREACH_BASE_URL is not set, sending is disabled."),
                messages.ERROR,
            )
            return None
        mailer = ProspectMailer(base_url=base_url, actor=request.user.get_username())
        plan = mailer.plan(queryset)
        if not plan.recipients:
            self.message_user(
                request, _("None of the selected prospects can be mailed."), messages.WARNING
            )
            return None

        step = request.POST.get("step")
        form = MessageForm(request.POST) if step else MessageForm()
        requested_step = step
        if step and not form.is_valid():
            step = None

        permissions = self.template_permissions(request)
        selected_template = None
        template_applied = False
        save_template_form = SaveTemplateForm()
        if requested_step == STEP_COMPOSE and request.POST.get("apply_template"):
            selected_template = self.template_to_apply(request, permissions["view"])
            if selected_template is not None:
                form = MessageForm(
                    initial={
                        "subject": selected_template.subject,
                        "body": selected_template.body_html,
                    }
                )
                template_applied = True
        elif requested_step == STEP_SAVE_TEMPLATE:
            save_template_form = SaveTemplateForm(request.POST)
            selected_template = self.save_template(
                request, form, save_template_form, permissions
            )
            if selected_template is not None:
                save_template_form = SaveTemplateForm()

        if step == STEP_SEND:
            subject = form.cleaned_data["subject"]
            report = mailer.send(queryset, subject, form.cleaned_data["body"])
            level = messages.WARNING if report.failed else messages.SUCCESS
            self.message_user(
                request,
                _("%(sent)d sent, %(skipped)d skipped, %(failed)d failed.")
                % {
                    "sent": len(report.sent),
                    "skipped": len(report.skipped),
                    "failed": len(report.failed),
                },
                level,
            )
            return None

        select_across = request.POST.get("select_across", "0").lower() not in FALSE_VALUES
        context = {
            **self.admin_site.each_context(request),
            "title": _("Send a mail"),
            "subtitle": None,
            "opts": self.model._meta,
            "form": form,
            "plan": plan,
            "queryset_ids": request.POST.getlist(helpers.ACTION_CHECKBOX_NAME),
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "select_across": int(select_across),
            "max_recipients": outreach_settings.max_recipients_per_send,
            "media": self.media,
            "email_templates": self.template_choices(permissions["view"]),
            "selected_template": selected_template,
            "template_applied": template_applied,
            "save_template_form": save_template_form,
            "can_save_template": permissions["add"],
            "can_overwrite_template": permissions["change"],
        }
        if step == STEP_PREVIEW:
            recipients_by_pk = {str(prospect.pk): prospect for prospect in plan.recipients}
            preview_prospect = recipients_by_pk.get(
                request.POST.get("preview_prospect", ""), plan.recipients[0]
            )
            subject = form.cleaned_data["subject"]
            try:
                rendered = mailer.render(
                    preview_prospect, subject, form.cleaned_data["body"], preview=True
                )
            except InvalidButtonLink as error:
                form.add_error("body", str(error))
                return TemplateResponse(request, "outreach/admin/compose.html", context)
            context.update(
                preview_prospect=preview_prospect,
                preview_html=rendered.html,
                preview_subject=rendered.subject,
                subject=subject,
                preview_choices=[
                    (str(prospect.pk), prospect.display_name) for prospect in plan.recipients
                ],
            )
            return TemplateResponse(request, "outreach/admin/preview.html", context)
        return TemplateResponse(request, "outreach/admin/compose.html", context)

    def template_permissions(self, request: HttpRequest) -> dict[str, bool]:
        return {
            action: request.user.has_perm(f"outreach.{action}_emailtemplate")
            for action in ("view", "add", "change")
        }

    def template_choices(self, can_view: bool) -> list[tuple[str, str]]:
        if not can_view:
            return []
        return [(str(template.pk), template.name) for template in EmailTemplate.objects.all()]

    def template_to_apply(self, request: HttpRequest, can_view: bool) -> EmailTemplate | None:
        template = None
        if can_view:
            try:
                template = EmailTemplate.objects.filter(
                    pk=request.POST.get("template")
                ).first()
            except (ValidationError, ValueError):
                template = None
        if template is None:
            self.message_user(request, _("That template is not available."), messages.ERROR)
        return template

    def name_taken_message(self, name: str, can_overwrite: bool) -> str:
        if can_overwrite:
            message = _(
                "A template named “%(name)s” already exists. Tick the box to replace it."
            )
        else:
            message = _("A template named “%(name)s” already exists.")
        return message % {"name": name}

    def save_template(
        self,
        request: HttpRequest,
        message_form: MessageForm,
        save_template_form: SaveTemplateForm,
        permissions: dict[str, bool],
    ) -> EmailTemplate | None:
        if not permissions["add"]:
            self.message_user(request, _("You may not add templates."), messages.ERROR)
            return None
        if not (message_form.is_valid() and save_template_form.is_valid()):
            return None
        name = save_template_form.cleaned_data["name"]
        overwrite = save_template_form.cleaned_data["overwrite"]
        name_taken = EmailTemplate.objects.filter(name__iexact=name.strip()).exists()
        if name_taken and not overwrite and not permissions["change"]:
            save_template_form.add_error(
                "name", self.name_taken_message(name.strip(), permissions["change"])
            )
            return None
        if name_taken and overwrite and not permissions["change"]:
            self.message_user(request, _("You may not replace templates."), messages.ERROR)
            return None
        try:
            saved = EmailTemplates().save(
                name,
                message_form.cleaned_data["subject"],
                message_form.cleaned_data["body"],
                request.user.get_username(),
                overwrite,
            )
        except TemplateNameTaken:
            save_template_form.add_error(
                "name", self.name_taken_message(name.strip(), permissions["change"])
            )
            return None
        self.message_user(request, _("Template saved."), messages.SUCCESS)
        return saved.template

    @admin.action(
        description=gettext_lazy("Unsubscribe the selected prospects"),
        permissions=["change"],
    )
    def unsubscribe_selected(self, request: HttpRequest, queryset: QuerySet[Prospect]) -> None:
        unsubscriber = ProspectUnsubscriber()
        actor = request.user.get_username()
        count = 0
        for prospect in queryset.exclude(status=ProspectStatus.UNSUBSCRIBED):
            unsubscriber.unsubscribe(prospect, actor)
            count += 1
        message = ngettext(
            "%(count)d prospect unsubscribed.", "%(count)d prospects unsubscribed.", count
        )
        self.message_user(request, message % {"count": count}, messages.SUCCESS)

    @admin.action(
        description=gettext_lazy("Link to user accounts"),
        permissions=["change"],
    )
    def link_users(self, request: HttpRequest, queryset: QuerySet[Prospect]) -> None:
        linker = UserLinker()
        count = 0
        for prospect in queryset.filter(user__isnull=True):
            if linker.link(prospect):
                prospect.save(update_fields=["user", "updated_at"])
                ProspectEvent.record(prospect, EventKind.LINKED, ACTOR_SYSTEM)
                count += 1
        message = ngettext("%(count)d prospect linked.", "%(count)d prospects linked.", count)
        self.message_user(request, message % {"count": count}, messages.SUCCESS)
