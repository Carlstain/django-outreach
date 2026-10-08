from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.services.body import MailBodySanitizer
from outreach.services.variables import MailVariables


class MessageContentForm:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    def raise_for_variable_problems(self, text: str) -> None:
        variables = MailVariables()
        unknown_keys = variables.unknown_keys(text)
        if unknown_keys:
            raise forms.ValidationError(
                _("Unknown variable(s): %(unknown)s. Use one of: %(allowed)s."),
                params={
                    "unknown": ", ".join(sorted(unknown_keys)),
                    "allowed": ", ".join(variables.KEYS),
                },
            )
        if variables.has_malformed_braces(text):
            raise forms.ValidationError(
                _("Malformed variable: check the braces around {{ ... }}.")
            )

    def clean_subject(self) -> str:
        subject = self.cleaned_data["subject"]
        if "\n" in subject or "\r" in subject:
            raise forms.ValidationError(_("The subject must be on a single line."))
        self.raise_for_variable_problems(subject)
        return subject

    def clean_body_content(self, field_name: str) -> str:
        sanitizer = MailBodySanitizer()
        body_html = sanitizer.clean(self.cleaned_data[field_name])
        if not sanitizer.to_text(body_html).strip():
            raise forms.ValidationError(_("The message is empty."))
        self.raise_for_variable_problems(body_html)
        return body_html
