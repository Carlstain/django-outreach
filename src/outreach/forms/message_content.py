from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.services.body import MailBodySanitizer
from outreach.services.mail_buttons import mail_buttons
from outreach.services.mail_tags import mail_tag_library
from outreach.services.variables import MailVariables


class MessageContentForm:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)

    def raise_for_variable_problems(self, text: str) -> None:
        variables = MailVariables()
        unknown_keys = variables.unknown_keys(text) | mail_tag_library.unknown_variables(
            text, variables.allowed_keys()
        )
        if unknown_keys:
            raise forms.ValidationError(
                _("Unknown variable(s): %(unknown)s. Use one of: %(allowed)s."),
                params={
                    "unknown": ", ".join(sorted(unknown_keys)),
                    "allowed": ", ".join(variable.key for variable in variables.catalog()),
                },
            )
        if variables.has_malformed_braces(text):
            raise forms.ValidationError(
                _("Malformed variable: check the braces around {{ ... }}.")
            )

    def raise_for_tag_problems(self, text: str) -> None:
        unknown_names = mail_tag_library.unknown_names(text)
        if unknown_names:
            raise forms.ValidationError(
                _("Unknown tag(s): %(unknown)s. Use one of: %(allowed)s."),
                params={
                    "unknown": ", ".join(sorted(unknown_names)),
                    "allowed": ", ".join(tag.name for tag in mail_tag_library.catalog()),
                },
            )
        invalid_calls = mail_tag_library.invalid_calls(text)
        if invalid_calls:
            raise forms.ValidationError(
                _("Invalid arguments for tag(s): %(tags)s."),
                params={"tags": ", ".join(sorted(invalid_calls))},
            )
        if mail_tag_library.has_malformed_delimiters(text):
            raise forms.ValidationError(
                _("Malformed tag: check the delimiters around {% ... %}.")
            )

    def raise_for_button_problems(self, text: str) -> None:
        if mail_buttons.has_misplaced_buttons(text):
            raise forms.ValidationError(
                _("A button cannot be placed inside a link or another tag.")
            )
        if mail_buttons.has_invalid_buttons(text):
            raise forms.ValidationError(
                _(
                    "Invalid button: a button needs a label and one link "
                    "(http, https or mailto, a variable or a tag)."
                )
            )

    def clean_subject(self) -> str:
        subject = self.cleaned_data["subject"]
        if "\n" in subject or "\r" in subject:
            raise forms.ValidationError(_("The subject must be on a single line."))
        self.raise_for_variable_problems(subject)
        self.raise_for_tag_problems(subject)
        if mail_buttons.contains_button(subject):
            raise forms.ValidationError(_("Buttons can only be used in the message body."))
        return subject

    def clean_header_text(self) -> str:
        header_text = self.cleaned_data["header_text"].strip()
        if "\n" in header_text or "\r" in header_text:
            raise forms.ValidationError(_("The header text must be on a single line."))
        return header_text

    def clean_body_content(self, field_name: str) -> str:
        sanitizer = MailBodySanitizer()
        body_html = sanitizer.clean(self.cleaned_data[field_name])
        if not sanitizer.to_text(body_html).strip():
            raise forms.ValidationError(_("The message is empty."))
        is_notice = not self.cleaned_data.get("is_newsletter")
        if is_notice and "unsubscribe_url" in MailVariables().used_keys(body_html):
            raise forms.ValidationError(
                _("A notice has no unsubscribe link: remove {{ unsubscribe_url }}.")
            )
        self.raise_for_variable_problems(body_html)
        self.raise_for_tag_problems(body_html)
        self.raise_for_button_problems(body_html)
        return body_html
