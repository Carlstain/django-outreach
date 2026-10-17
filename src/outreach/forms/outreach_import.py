from typing import Any

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _

from outreach.conf import outreach_settings


class OutreachImportForm(forms.Form):
    use_required_attribute = False

    import_file = forms.FileField(label=_("CSV file"))
    update_existing = forms.BooleanField(
        required=False,
        label=_("Update the prospects that already exist"),
        help_text=_(
            "A filled cell of the file replaces the stored value, an empty cell changes "
            "nothing. The email, status, account link and audiences are never changed."
        ),
    )

    def __init__(self, *args: Any, can_update: bool = True, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        if not can_update:
            del self.fields["update_existing"]

    def clean_import_file(self) -> UploadedFile:
        import_file = self.cleaned_data["import_file"]
        limit = outreach_settings.max_import_bytes
        if import_file.size > limit:
            raise forms.ValidationError(
                _("The file is %(size)d bytes, the limit is %(limit)d."),
                params={"size": import_file.size, "limit": limit},
            )
        return import_file
