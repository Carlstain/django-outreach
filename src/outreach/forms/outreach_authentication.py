from typing import Any

from django.contrib.admin.forms import AdminAuthenticationForm


class OutreachAuthenticationForm(AdminAuthenticationForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
