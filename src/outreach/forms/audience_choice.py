from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.forms.audience import AUDIENCE_NAME_TAKEN
from outreach.models import Audience


class AudienceChoiceForm(forms.Form):
    """Picks the audience of a bulk action, or names a new one when ``creating``."""

    audience = forms.ModelChoiceField(
        queryset=Audience.objects.all(), empty_label=None, label=_("Audience")
    )
    new_audience_name = forms.CharField(
        max_length=Audience._meta.get_field("name").max_length,
        required=False,
        label=_("Or create a new audience"),
    )

    def __init__(self, *args: Any, creating: bool = False, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        if creating:
            self.fields["audience"].required = False
            self.fields["audience"].empty_label = _("Choose an audience")
        else:
            del self.fields["new_audience_name"]

    def clean_new_audience_name(self) -> str:
        name = self.cleaned_data["new_audience_name"]
        if name and Audience.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError(AUDIENCE_NAME_TAKEN)
        return name

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if "new_audience_name" not in self.fields or self.errors:
            return cleaned_data
        has_audience = cleaned_data["audience"] is not None
        has_name = bool(cleaned_data["new_audience_name"])
        if has_audience and has_name:
            raise forms.ValidationError(_("Choose an audience or type a new name, not both."))
        if not has_audience and not has_name:
            raise forms.ValidationError(
                _("Choose an audience, or type the name of a new one.")
            )
        return cleaned_data
