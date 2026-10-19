from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.conf import outreach_settings
from outreach.forms.audience_choice import AudienceChoiceForm


class OutreachImportConfirmForm(AudienceChoiceForm):
    audience_required = False

    csv_text = forms.CharField(widget=forms.HiddenInput)
    file_name = forms.CharField(widget=forms.HiddenInput, max_length=255)
    update_existing = forms.BooleanField(required=False, widget=forms.HiddenInput)
    audience_lines = forms.TypedMultipleChoiceField(required=False, coerce=int)

    def __init__(self, *args: Any, can_choose_audience: bool = True, **kwargs: Any) -> None:
        super().__init__(*args, creating=True, **kwargs)
        self.fields["audience"].label = _("Add the imported rows to an audience")
        posted_lines = self.data.getlist("audience_lines") if self.is_bound else []
        self.fields["audience_lines"].choices = [(line, line) for line in posted_lines]
        if not can_choose_audience:
            for field_name in ("audience", "new_audience_name", "audience_lines"):
                del self.fields[field_name]

    def clean_csv_text(self) -> str:
        csv_text = self.cleaned_data["csv_text"]
        if len(csv_text.encode()) > outreach_settings.max_import_bytes:
            raise forms.ValidationError(_("The file is too large."))
        return csv_text
