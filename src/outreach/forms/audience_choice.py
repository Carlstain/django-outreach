from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.models import Audience


class AudienceChoiceForm(forms.Form):
    audience = forms.ModelChoiceField(
        queryset=Audience.objects.all(), empty_label=None, label=_("Audience")
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
