from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.db.models.query import QuerySet

from outreach.forms import EmailTemplateForm
from outreach.models import EmailTemplate
from outreach.services.templates import EmailTemplates, TemplateNameTaken
from tests.base import OutreachTestCase
from tests.factories import EmailTemplateFactory, UserFactory


def template_form(**overrides: str) -> EmailTemplateForm:
    data = {"name": "Welcome", "subject": "Hello", "body_html": "<p>Body</p>", **overrides}
    return EmailTemplateForm(data)


class EmailTemplateModelTests(OutreachTestCase):
    def test_valid_form_saves_a_template(self) -> None:
        form = template_form()

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(
            (saved.name, saved.subject, saved.body_html), ("Welcome", "Hello", "<p>Body</p>")
        )

    def test_name_must_be_unique_ignoring_case(self) -> None:
        EmailTemplateFactory(name="Welcome")

        form = template_form(name="wELCOME")

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["name"], ["A template with this name already exists."])

    def test_database_refuses_names_that_differ_only_by_case(self) -> None:
        EmailTemplateFactory(name="Welcome")

        with self.assertRaises(IntegrityError), transaction.atomic():
            EmailTemplate.objects.create(name="WELCOME", subject="s", body_html="<p>b</p>")

        self.assertEqual(EmailTemplate.objects.count(), 1)

    def test_editing_a_template_keeps_its_own_name_valid(self) -> None:
        existing = EmailTemplateFactory(name="Welcome")
        form = EmailTemplateForm(
            {"name": "Welcome", "subject": "New", "body_html": "<p>New</p>"}, instance=existing
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_subject_must_be_a_single_line(self) -> None:
        form = template_form(subject="Hello\nWorld")

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["subject"], ["The subject must be on a single line."])

    def test_unknown_variable_in_the_subject_is_rejected(self) -> None:
        form = template_form(subject="Hello {{ nickname }}")

        self.assertEqual(
            form.errors["subject"],
            [
                "Unknown variable(s): nickname. Use one of: first_name, last_name, "
                "full_name, organization, email, city, country."
            ],
        )

    def test_unknown_variable_in_the_body_is_rejected(self) -> None:
        form = template_form(body_html="<p>Dear {{ firstname }}</p>")

        self.assertEqual(
            form.errors["body_html"],
            [
                "Unknown variable(s): firstname. Use one of: first_name, last_name, "
                "full_name, organization, email, city, country."
            ],
        )

    def test_malformed_variable_is_rejected(self) -> None:
        form = template_form(body_html="<p>Dear {{ first_name }</p>")

        self.assertEqual(
            form.errors["body_html"],
            ["Malformed variable: check the braces around {{ ... }}."],
        )

    def test_body_is_sanitised_by_the_form(self) -> None:
        form = template_form(body_html='<p onclick="x()">Hi</p><script>alert(1)</script>')

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["body_html"], "<p>Hi</p>")

    def test_empty_body_is_rejected(self) -> None:
        form = template_form(body_html="<p> </p>")

        self.assertEqual(form.errors["body_html"], ["The message is empty."])

    def test_service_records_the_author_on_creation(self) -> None:
        author = UserFactory()

        saved = EmailTemplates().save(
            "Welcome", "Hello", "<p>Body</p>", author, overwrite=False
        )

        saved.template.refresh_from_db()
        self.assertEqual(saved.template.created_by, author)
        self.assertEqual(saved.template.updated_by, author)

    def test_overwriting_sets_updated_by_and_keeps_created_by(self) -> None:
        creator = UserFactory()
        editor = UserFactory()
        EmailTemplateFactory(name="Welcome", created_by=creator, updated_by=creator)

        saved = EmailTemplates().save(
            "welcome", "Hello", "<p>Body</p>", editor, overwrite=True
        )

        saved.template.refresh_from_db()
        self.assertEqual(saved.template.created_by, creator)
        self.assertEqual(saved.template.updated_by, editor)

    def test_deleting_the_author_clears_the_author_fields(self) -> None:
        author = UserFactory()
        template = EmailTemplateFactory(created_by=author, updated_by=author)

        author.delete()

        template.refresh_from_db()
        self.assertIsNone(template.created_by)
        self.assertIsNone(template.updated_by)

    def test_a_name_taken_between_lookup_and_create_is_reported_as_name_taken(self) -> None:
        EmailTemplateFactory(name="Welcome")

        with (
            patch.object(QuerySet, "first", return_value=None),
            self.assertRaises(TemplateNameTaken),
        ):
            EmailTemplates().save("welcome", "Hello", "<p>Body</p>", None, overwrite=False)

        self.assertEqual(EmailTemplate.objects.count(), 1)
