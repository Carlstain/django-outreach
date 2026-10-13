from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.models import Audience

AUDIENCE_NAME_TAKEN = _("An audience with this name already exists.")


class AudienceForm(forms.ModelForm):
    class Meta:
        model = Audience
        fields = ["name", "description"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        clashing_audiences = Audience.objects.filter(name__iexact=name).exclude(
            pk=self.instance.pk
        )
        if clashing_audiences.exists():
            raise forms.ValidationError(AUDIENCE_NAME_TAKEN)
        return name
