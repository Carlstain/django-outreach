import json
from typing import Any

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext

from outreach.admin.audience_filter import AudienceFilter
from outreach.admin.member_filter import MemberFilter
from outreach.admin.prospect_event_inline import ProspectEventInline
from outreach.choices import ACTOR_SYSTEM, EventKind, ProspectKind, ProspectStatus
from outreach.conf import outreach_settings
from outreach.forms import (
    AUDIENCE_NAME_TAKEN,
    AudienceChoiceForm,
    MessageForm,
    OutreachImportConfirmForm,
    OutreachImportForm,
    ProspectForm,
    SaveTemplateForm,
)
from outreach.models import EmailTemplate, Prospect, ProspectEvent
from outreach.services.audiences import AudienceCreator, AudienceMembers, AudienceNameTaken
from outreach.services.erasure import ProspectEraser
from outreach.services.failures import MessageNotAccepted
from outreach.services.linking import UserLinker
from outreach.services.mail_buttons import InvalidButtonLink
from outreach.services.mailing import ProspectMailer
from outreach.services.prospect_csv import (
    CsvImportError,
    ProspectCsvColumns,
    ProspectCsvExporter,
    ProspectCsvImporter,
)
from outreach.services.prospect_export import ProspectDataExporter
from outreach.services.scheduling import MailingScheduler
from outreach.services.templates import EmailTemplates, TemplateNameTaken
from outreach.services.unsubscribe import ProspectUnsubscriber
from outreach.sites import outreach_site

STEP_PREVIEW = "preview"
STEP_SEND = "send"
STEP_TEST = "test"
STEP_COMPOSE = "compose"
STEP_SAVE_TEMPLATE = "save_template"
FALSE_VALUES = ("", "0", "false")
STATUS_BADGE_CLASSES = {
    ProspectStatus.PROSPECT: "prospect",
    ProspectStatus.CONTACTED: "contacted",
    ProspectStatus.UNSUBSCRIBED: "unsub",
}


@admin.register(Prospect, site=outreach_site)
class ProspectAdmin(admin.ModelAdmin):
    form = ProspectForm
    list_per_page = 20
    list_display = ["display_name", "email", "status_badge", "member", "last_mailed_at"]
    list_filter = ["kind", "status", MemberFilter, AudienceFilter]
    search_fields = ["email", "first_name", "last_name", "organization"]
    inlines = [ProspectEventInline]
    actions = [
        "send_mail",
        "add_to_audience",
        "remove_from_audience",
        "unsubscribe_selected",
        "erase_selected",
        "link_users",
        "export_csv",
    ]
    change_list_template = "outreach/admin/change_list.html"
    change_form_template = "outreach/admin/change_form.html"
    delete_confirmation_template = "outreach/admin/delete_confirmation.html"
    delete_selected_confirmation_template = "outreach/admin/delete_selected_confirmation.html"
    import_template_name = "outreach/admin/import.html"

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
            "audiences",
            "created_at",
            "updated_at",
        ]

    def get_readonly_fields(
        self, request: HttpRequest, obj: Prospect | None = None
    ) -> list[str]:
        readonly_fields = [
            "status",
            "last_mailed_at",
            "user",
            "audiences",
            "created_at",
            "updated_at",
        ]
        if obj is not None:
            readonly_fields.append("email")
        return readonly_fields

    def has_import_permission(self, request: HttpRequest) -> bool:
        return self.has_add_permission(request)

    def get_urls(self) -> list[URLPattern]:
        return [
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="outreach_prospect_import",
            ),
            path(
                "process_import/",
                self.admin_site.admin_view(self.process_import_view),
                name="outreach_prospect_process_import",
            ),
            path(
                "<path:object_id>/export-data/",
                self.admin_site.admin_view(self.export_data_view),
                name="outreach_prospect_export_data",
            ),
            *super().get_urls(),
        ]

    def export_data_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        if not self.has_view_permission(request):
            raise PermissionDenied
        prospect = self.get_object(request, object_id)
        if prospect is None:
            raise Http404
        response = HttpResponse(
            json.dumps(ProspectDataExporter().export(prospect), indent=2, ensure_ascii=False),
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="prospect-{prospect.pk}.json"'
        return response

    def import_response(self, request: HttpRequest, **context: Any) -> HttpResponse:
        return TemplateResponse(
            request,
            self.import_template_name,
            {
                **self.admin_site.each_context(request),
                "title": _("Import"),
                "subtitle": None,
                "opts": self.model._meta,
                "columns": ProspectCsvColumns().labels(),
                **context,
            },
        )

    def import_view(self, request: HttpRequest) -> HttpResponse:
        if not self.has_import_permission(request):
            raise PermissionDenied
        form = OutreachImportForm(request.POST or None, request.FILES or None)
        if request.method != "POST" or not form.is_valid():
            return self.import_response(request, form=form)
        upload = form.cleaned_data["import_file"]
        try:
            csv_text = upload.read().decode("utf-8-sig")
            preview = ProspectCsvImporter().preview(csv_text)
        except UnicodeDecodeError:
            form.add_error("import_file", _("The file must be UTF-8 text."))
            return self.import_response(request, form=form)
        except CsvImportError as error:
            form.add_error("import_file", str(error))
            return self.import_response(request, form=form)
        if preview.invalid_rows:
            return self.import_response(request, form=form, preview=preview)
        confirm_form = OutreachImportConfirmForm(
            initial={"csv_text": csv_text, "file_name": upload.name}
        )
        return self.import_response(
            request, form=form, preview=preview, confirm_form=confirm_form
        )

    def process_import_view(self, request: HttpRequest) -> HttpResponse:
        if not self.has_import_permission(request):
            raise PermissionDenied
        import_url = reverse("outreach_admin:outreach_prospect_import")
        confirm_form = OutreachImportConfirmForm(request.POST or None)
        if request.method != "POST" or not confirm_form.is_valid():
            return HttpResponseRedirect(import_url)
        importer = ProspectCsvImporter()
        try:
            preview = importer.preview(confirm_form.cleaned_data["csv_text"])
        except CsvImportError as error:
            self.message_user(request, str(error), messages.ERROR)
            return HttpResponseRedirect(import_url)
        if preview.invalid_rows:
            return self.import_response(request, form=OutreachImportForm(), preview=preview)
        created_count = importer.apply(preview, confirm_form.cleaned_data["file_name"])
        message = ngettext(
            "%(count)d prospect imported.", "%(count)d prospects imported.", created_count
        )
        skipped_message = ngettext(
            "%(count)d row skipped.", "%(count)d rows skipped.", preview.skipped_count
        )
        self.message_user(
            request,
            f"{message % {'count': created_count}} "
            f"{skipped_message % {'count': preview.skipped_count}}",
            messages.SUCCESS,
        )
        return HttpResponseRedirect(reverse("outreach_admin:outreach_prospect_changelist"))

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
        mailer = self.admin_site.mailer_for(request)
        if mailer is None:
            return None
        step = request.POST.get("step")
        form = MessageForm(request.POST) if step else MessageForm()
        requested_step = step
        if step and not form.is_valid():
            step = None
        is_newsletter = True
        if requested_step:
            posted_flag = request.POST.get("is_newsletter", "")
            is_newsletter = posted_flag.lower() not in FALSE_VALUES

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
                        "header_text": selected_template.header_text,
                        "is_newsletter": selected_template.is_newsletter,
                        "body": selected_template.body_html,
                    }
                )
                is_newsletter = selected_template.is_newsletter
                template_applied = True
        elif requested_step == STEP_SAVE_TEMPLATE:
            save_template_form = SaveTemplateForm(request.POST)
            selected_template = self.save_template(
                request, form, save_template_form, permissions
            )
            if selected_template is not None:
                save_template_form = SaveTemplateForm()

        plan = mailer.plan(queryset, is_newsletter=is_newsletter)
        other_type_plan = mailer.plan(queryset, is_newsletter=not is_newsletter)
        if not plan.recipients and not other_type_plan.recipients:
            self.message_user(
                request, _("None of the selected prospects can be mailed."), messages.WARNING
            )
            return None
        if not plan.recipients and step:
            form.add_error(
                "is_newsletter",
                _("None of the selected prospects can receive this type of mail."),
            )
            step = None

        message_fields = {}
        if step in (STEP_PREVIEW, STEP_TEST, STEP_SEND):
            message_fields = {
                "header_text": form.cleaned_data["header_text"],
                "is_newsletter": form.cleaned_data["is_newsletter"],
            }

        if step == STEP_SEND:
            subject = form.cleaned_data["subject"]
            send_at = form.cleaned_data.get("send_at")
            if send_at:
                report = MailingScheduler(mailer).schedule(
                    queryset,
                    subject,
                    form.cleaned_data["body"],
                    send_at=send_at,
                    **message_fields,
                )
            else:
                report = mailer.send(
                    queryset, subject, form.cleaned_data["body"], **message_fields
                )
            self.message_user(request, *self.admin_site.report_message(report))
            return None

        context = {
            **self.admin_site.each_context(request),
            **self.selection_context(request),
            "title": _("Send a mail"),
            "subtitle": None,
            "opts": self.model._meta,
            "form": form,
            "plan": plan,
            "max_recipients": outreach_settings.recipient_cap,
            "media": self.media,
            "email_templates": self.template_choices(permissions["view"]),
            "selected_template": selected_template,
            "template_applied": template_applied,
            "save_template_form": save_template_form,
            "can_save_template": permissions["add"],
            "can_overwrite_template": permissions["change"],
        }
        if step in (STEP_PREVIEW, STEP_TEST):
            recipients_by_pk = {str(prospect.pk): prospect for prospect in plan.recipients}
            preview_prospect = recipients_by_pk.get(
                request.POST.get("preview_prospect", ""), plan.recipients[0]
            )
            subject = form.cleaned_data["subject"]
            try:
                rendered = mailer.render(
                    preview_prospect,
                    subject,
                    form.cleaned_data["body"],
                    preview=True,
                    **message_fields,
                )
            except InvalidButtonLink as error:
                form.add_error("body", str(error))
                return TemplateResponse(request, "outreach/admin/compose.html", context)
            if step == STEP_TEST:
                self.send_test_mail(request, mailer, preview_prospect, form, message_fields)
            context.update(
                preview_prospect=preview_prospect,
                preview_html=rendered.html,
                preview_subject=rendered.subject,
                subject=subject,
                send_at=form.cleaned_data.get("send_at"),
                preview_choices=[
                    (str(prospect.pk), prospect.display_name) for prospect in plan.recipients
                ],
            )
            return TemplateResponse(request, "outreach/admin/preview.html", context)
        return TemplateResponse(request, "outreach/admin/compose.html", context)

    def send_test_mail(
        self,
        request: HttpRequest,
        mailer: ProspectMailer,
        prospect: Prospect,
        form: MessageForm,
        message_fields: dict[str, Any],
    ) -> None:
        recipient_email = getattr(request.user, request.user.get_email_field_name(), "")
        if not recipient_email:
            self.message_user(
                request,
                _("Your account has no email address, so a test can not be sent."),
                messages.ERROR,
            )
            return
        try:
            mailer.send_sample(
                prospect,
                form.cleaned_data["subject"],
                form.cleaned_data["body"],
                recipient_email,
                **message_fields,
            )
        except (OSError, MessageNotAccepted):
            self.message_user(
                request,
                _("The test could not be sent. Check the mail settings."),
                messages.ERROR,
            )
            return
        self.message_user(
            request,
            _("A test was sent to %(email)s.") % {"email": recipient_email},
            messages.SUCCESS,
        )

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
                request.user,
                overwrite,
                header_text=message_form.cleaned_data["header_text"],
                is_newsletter=message_form.cleaned_data["is_newsletter"],
            )
        except TemplateNameTaken:
            save_template_form.add_error(
                "name", self.name_taken_message(name.strip(), permissions["change"])
            )
            return None
        self.message_user(request, _("Template saved."), messages.SUCCESS)
        return saved.template

    @admin.action(
        description=gettext_lazy("Add the selected prospects to an audience"),
        permissions=["change"],
    )
    def add_to_audience(
        self, request: HttpRequest, queryset: QuerySet[Prospect]
    ) -> HttpResponse | None:
        return self.change_audience_members(request, queryset, adding=True)

    @admin.action(
        description=gettext_lazy("Remove the selected prospects from an audience"),
        permissions=["change"],
    )
    def remove_from_audience(
        self, request: HttpRequest, queryset: QuerySet[Prospect]
    ) -> HttpResponse | None:
        return self.change_audience_members(request, queryset, adding=False)

    def selection_context(self, request: HttpRequest) -> dict[str, Any]:
        select_across = request.POST.get("select_across", "0").lower() not in FALSE_VALUES
        return {
            "queryset_ids": request.POST.getlist(helpers.ACTION_CHECKBOX_NAME),
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "select_across": int(select_across),
        }

    def change_audience_members(
        self, request: HttpRequest, queryset: QuerySet[Prospect], adding: bool
    ) -> HttpResponse | None:
        form = AudienceChoiceForm(
            request.POST if request.POST.get("apply") else None, creating=adding
        )
        if form.is_valid() and self.apply_audience_change(request, form, queryset, adding):
            return None
        context = {
            **self.admin_site.each_context(request),
            **self.selection_context(request),
            "title": _("Add to an audience") if adding else _("Remove from an audience"),
            "opts": self.model._meta,
            "form": form,
            "adding": adding,
            "action_name": "add_to_audience" if adding else "remove_from_audience",
            "selected_count": queryset.count(),
            "media": self.media,
        }
        return TemplateResponse(request, "outreach/admin/audience_choice.html", context)

    def apply_audience_change(
        self,
        request: HttpRequest,
        form: AudienceChoiceForm,
        queryset: QuerySet[Prospect],
        adding: bool,
    ) -> bool:
        audience = form.cleaned_data["audience"]
        is_new_audience = audience is None
        members = AudienceMembers()
        actor = request.user.get_username()
        try:
            with transaction.atomic():
                if is_new_audience:
                    audience = AudienceCreator().create(
                        form.cleaned_data["new_audience_name"], request.user
                    )
                if adding:
                    count = members.add(audience, queryset, actor)
                else:
                    count = members.remove(audience, queryset, actor)
        except AudienceNameTaken:
            form.add_error("new_audience_name", AUDIENCE_NAME_TAKEN)
            return False
        if is_new_audience:
            self.message_user(
                request,
                _("The audience %(audience)s was created.") % {"audience": audience},
                messages.SUCCESS,
            )
        if adding:
            message = ngettext(
                "%(count)d prospect added to %(audience)s.",
                "%(count)d prospects added to %(audience)s.",
                count,
            )
        else:
            message = ngettext(
                "%(count)d prospect removed from %(audience)s.",
                "%(count)d prospects removed from %(audience)s.",
                count,
            )
        self.message_user(
            request, message % {"count": count, "audience": audience}, messages.SUCCESS
        )
        return True

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
        description=gettext_lazy("Erase and suppress the selected prospects"),
        permissions=["delete"],
    )
    def erase_selected(
        self, request: HttpRequest, queryset: QuerySet[Prospect]
    ) -> HttpResponse | None:
        if request.POST.get("apply"):
            count = ProspectEraser().erase(queryset, request.user.get_username())
            message = ngettext(
                "%(count)d prospect erased and suppressed.",
                "%(count)d prospects erased and suppressed.",
                count,
            )
            self.message_user(request, message % {"count": count}, messages.SUCCESS)
            return None
        context = {
            **self.admin_site.each_context(request),
            **self.selection_context(request),
            "title": _("Erase and suppress"),
            "opts": self.model._meta,
            "action_name": "erase_selected",
            "selected_count": queryset.count(),
            "media": self.media,
        }
        return TemplateResponse(request, "outreach/admin/erase_confirmation.html", context)

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

    @admin.action(
        description=gettext_lazy("Export the selected prospects as CSV"),
        permissions=["view"],
    )
    def export_csv(self, request: HttpRequest, queryset: QuerySet[Prospect]) -> HttpResponse:
        response = HttpResponse(
            ProspectCsvExporter().to_csv(queryset.iterator()),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = 'attachment; filename="prospects.csv"'
        return response
