from dataclasses import dataclass

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import IntegrityError, transaction

from outreach.models import EmailTemplate
from outreach.services.body import MailBodySanitizer


class TemplateNameTaken(Exception):
    """A template with that name (ignoring case) exists and ``overwrite`` was not allowed."""


@dataclass(frozen=True)
class SavedTemplate:
    """The saved template and whether it was created, as opposed to overwritten."""

    template: EmailTemplate
    created: bool


class EmailTemplates:
    def save(
        self,
        name: str,
        subject: str,
        body_html: str,
        author: AbstractBaseUser | None,
        overwrite: bool,
        *,
        header_text: str = "",
        is_newsletter: bool = True,
        language: str = "",
    ) -> SavedTemplate:
        """Create a template, or update the one with the same name when ``overwrite`` is true.

        The body is sanitised. Overwriting keeps ``created_by`` and sets ``updated_by`` to the
        author.

        Raises:
            TemplateNameTaken: The name is taken and ``overwrite`` is false.
        """
        clean_name = name.strip()
        clean_body = MailBodySanitizer().clean(body_html)
        existing = EmailTemplate.objects.filter(name__iexact=clean_name).first()
        if existing is None:
            try:
                return self.create(
                    clean_name,
                    subject,
                    clean_body,
                    author,
                    header_text=header_text,
                    is_newsletter=is_newsletter,
                    language=language,
                )
            except IntegrityError as error:
                existing = EmailTemplate.objects.filter(name__iexact=clean_name).first()
                if existing is None or not overwrite:
                    raise TemplateNameTaken(clean_name) from error
        if not overwrite:
            raise TemplateNameTaken(clean_name)
        existing.subject = subject
        existing.body_html = clean_body
        existing.header_text = header_text
        existing.is_newsletter = is_newsletter
        existing.language = language
        existing.updated_by = author
        existing.save(
            update_fields=[
                "subject",
                "body_html",
                "header_text",
                "is_newsletter",
                "language",
                "updated_by",
                "updated_at",
            ]
        )
        return SavedTemplate(existing, created=False)

    def create(
        self,
        name: str,
        subject: str,
        body_html: str,
        author: AbstractBaseUser | None,
        *,
        header_text: str = "",
        is_newsletter: bool = True,
        language: str = "",
    ) -> SavedTemplate:
        with transaction.atomic():
            template = EmailTemplate.objects.create(
                name=name,
                subject=subject,
                body_html=body_html,
                header_text=header_text,
                is_newsletter=is_newsletter,
                language=language,
                created_by=author,
                updated_by=author,
            )
        return SavedTemplate(template, created=True)
