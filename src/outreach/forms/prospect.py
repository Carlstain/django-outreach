from typing import Any

from django import forms


class ProspectForm(forms.ModelForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
