from datetime import datetime
from typing import Any

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from outreach.conf import outreach_settings
from outreach.forms.message_content import MessageContentForm
from outreach.widgets import TrixWidget


class MessageForm(MessageContentForm, forms.Form):
    use_required_attribute = False

    subject = forms.CharField(max_length=200, label=_("Subject"))
    header_text = forms.CharField(max_length=120, required=False, label=_("Header text"))
    is_newsletter = forms.BooleanField(required=False, initial=True, label=_("Newsletter"))
    body = forms.CharField(max_length=100000, widget=TrixWidget, label=_("Message"))
    send_at = forms.DateTimeField(
        required=False,
        label=_("Send at"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not outreach_settings.uses_celery:
            del self.fields["send_at"]

    def clean_send_at(self) -> datetime | None:
        send_at = self.cleaned_data["send_at"]
        if send_at is not None and send_at <= timezone.now():
            raise forms.ValidationError(_("Choose a time in the future."))
        return send_at

    def clean_body(self) -> str:
        return self.clean_body_content("body")
