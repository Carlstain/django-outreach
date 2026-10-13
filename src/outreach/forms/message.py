from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.forms.message_content import MessageContentForm
from outreach.widgets import TrixWidget


class MessageForm(MessageContentForm, forms.Form):
    use_required_attribute = False

    subject = forms.CharField(max_length=200, label=_("Subject"))
    header_text = forms.CharField(max_length=120, required=False, label=_("Header text"))
    is_newsletter = forms.BooleanField(required=False, initial=True, label=_("Newsletter"))
    body = forms.CharField(max_length=100000, widget=TrixWidget, label=_("Message"))

    def clean_body(self) -> str:
        return self.clean_body_content("body")
