from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.conf import outreach_settings


class OutreachImportConfirmForm(forms.Form):
    csv_text = forms.CharField(widget=forms.HiddenInput)
    file_name = forms.CharField(widget=forms.HiddenInput, max_length=255)
    update_existing = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def clean_csv_text(self) -> str:
        csv_text = self.cleaned_data["csv_text"]
        if len(csv_text.encode()) > outreach_settings.max_import_bytes:
            raise forms.ValidationError(_("The file is too large."))
        return csv_text
