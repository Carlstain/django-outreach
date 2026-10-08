from typing import Any

from import_export.forms import ImportForm


class OutreachImportForm(ImportForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
