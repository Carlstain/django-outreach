from typing import Any

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from import_export.forms import ImportForm

from outreach.conf import outreach_settings


class OutreachImportForm(ImportForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    def clean_import_file(self) -> UploadedFile:
        import_file = self.cleaned_data["import_file"]
        limit = outreach_settings.max_import_bytes
        if import_file.size > limit:
            raise forms.ValidationError(
                _("The file is %(size)d bytes, the limit is %(limit)d."),
                params={"size": import_file.size, "limit": limit},
            )
        return import_file
