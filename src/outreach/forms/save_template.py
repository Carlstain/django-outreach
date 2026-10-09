from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _


class SaveTemplateForm(forms.Form):
    use_required_attribute = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    name = forms.CharField(max_length=120, label=_("Template name"))
    overwrite = forms.BooleanField(
        required=False, label=_("Replace the template if it exists")
    )
