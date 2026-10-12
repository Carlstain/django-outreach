from typing import Any

from django import forms

from outreach.services.mail_tags import mail_tag_library
from outreach.services.variables import MailVariables

TRIX_VERSION = "2.1.19"


class TrixWidget(forms.Widget):
    template_name = "outreach/widgets/trix.html"

    class Media:
        css = {"all": [f"outreach/vendor/trix/trix-{TRIX_VERSION}.css"]}
        js = [
            f"outreach/vendor/trix/trix-{TRIX_VERSION}.umd.min.js",
            "outreach/mail-editor.js",
        ]

    def get_context(
        self, name: str, value: Any, attrs: dict[str, Any] | None
    ) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["variables"] = MailVariables().catalog()
        context["mail_tags"] = mail_tag_library.catalog()
        return context
