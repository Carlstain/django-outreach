from dataclasses import dataclass

from django.db import IntegrityError, transaction

from outreach.models import EmailTemplate
from outreach.services.body import MailBodySanitizer


class TemplateNameTaken(Exception):
    pass


@dataclass(frozen=True)
class SavedTemplate:
    template: EmailTemplate
    created: bool


class EmailTemplates:
    def save(
        self, name: str, subject: str, body_html: str, author: str, overwrite: bool
    ) -> SavedTemplate:
        clean_name = name.strip()
        clean_body = MailBodySanitizer().clean(body_html)
        existing = EmailTemplate.objects.filter(name__iexact=clean_name).first()
        if existing is None:
            try:
                return self.create(clean_name, subject, clean_body, author)
            except IntegrityError as error:
                existing = EmailTemplate.objects.filter(name__iexact=clean_name).first()
                if existing is None or not overwrite:
                    raise TemplateNameTaken(clean_name) from error
        if not overwrite:
            raise TemplateNameTaken(clean_name)
        existing.subject = subject
        existing.body_html = clean_body
        existing.save(update_fields=["subject", "body_html", "updated_at"])
        return SavedTemplate(existing, created=False)

    def create(self, name: str, subject: str, body_html: str, author: str) -> SavedTemplate:
        author_max_length = EmailTemplate._meta.get_field("created_by").max_length
        with transaction.atomic():
            template = EmailTemplate.objects.create(
                name=name,
                subject=subject,
                body_html=body_html,
                created_by=author[:author_max_length],
            )
        return SavedTemplate(template, created=True)
