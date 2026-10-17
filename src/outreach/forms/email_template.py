from django import forms
from django.utils.translation import gettext_lazy as _

from outreach.forms.message_content import MessageContentForm
from outreach.models import EmailTemplate
from outreach.widgets import TrixWidget


class EmailTemplateForm(MessageContentForm, forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ["name", "subject", "header_text", "is_newsletter", "language", "body_html"]
        widgets = {"body_html": TrixWidget}

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        clashing_templates = EmailTemplate.objects.filter(name__iexact=name).exclude(
            pk=self.instance.pk
        )
        if clashing_templates.exists():
            raise forms.ValidationError(_("A template with this name already exists."))
        return name

    def clean_body_html(self) -> str:
        return self.clean_body_content("body_html")
