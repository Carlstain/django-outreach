from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.forms.models import BaseModelForm
from django.urls import reverse

from outreach.models import EmailTemplate
from tests.base import OutreachTestCase
from tests.factories import (
    OUTREACH_TEMPLATE_PERMISSIONS,
    EmailTemplateFactory,
    create_outreach_staff_user,
)
from tests.html_inspector import inspect_page
from tests.routes import (
    outreach_emailtemplate_add_url,
    outreach_emailtemplate_change_url,
    outreach_emailtemplate_changelist_url,
    outreach_emailtemplate_delete_url,
)

FORM_FIELDS = {
    "name": "Welcome",
    "subject": "Hello {{ first_name }}",
    "body_html": "<p>Body</p>",
}


def staff_with(*template_codenames: str) -> AbstractBaseUser:
    return create_outreach_staff_user(["view_prospect", *template_codenames])


class EmailTemplateAdminTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user(
            ["view_prospect", *OUTREACH_TEMPLATE_PERMISSIONS]
        )
        self.client.force_login(self.staff_user)

    def test_changelist_lists_templates_by_name(self) -> None:
        second = EmailTemplateFactory(name="Second")
        first = EmailTemplateFactory(name="First")

        response = self.client.get(outreach_emailtemplate_changelist_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["cl"].result_list), [first, second])

    def test_search_matches_name_and_subject(self) -> None:
        by_name = EmailTemplateFactory(name="Quarterly update")
        by_subject = EmailTemplateFactory(subject="Autumn offer")
        EmailTemplateFactory()

        name_response = self.client.get(
            outreach_emailtemplate_changelist_url(), {"q": "quarterly"}
        )
        subject_response = self.client.get(
            outreach_emailtemplate_changelist_url(), {"q": "autumn"}
        )

        self.assertEqual(list(name_response.context["cl"].result_list), [by_name])
        self.assertEqual(list(subject_response.context["cl"].result_list), [by_subject])

    def test_add_creates_a_template_authored_by_the_user(self) -> None:
        response = self.client.post(
            outreach_emailtemplate_add_url(),
            {**FORM_FIELDS, "body_html": "<p>Body</p><script>alert(1)</script>"},
        )

        self.assertEqual(response.status_code, 302)
        template = EmailTemplate.objects.get()
        self.assertEqual(template.name, "Welcome")
        self.assertEqual(template.body_html, "<p>Body</p>")
        self.assertEqual(template.created_by, self.staff_user.get_username())

    def test_change_updates_the_template_and_keeps_its_author(self) -> None:
        template = EmailTemplateFactory(created_by="original-author")

        response = self.client.post(
            outreach_emailtemplate_change_url(template.pk),
            {**FORM_FIELDS, "name": "Renamed"},
        )

        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertEqual(template.name, "Renamed")
        self.assertEqual(template.subject, "Hello {{ first_name }}")
        self.assertEqual(template.created_by, "original-author")

    def test_delete_removes_the_template(self) -> None:
        template = EmailTemplateFactory()

        response = self.client.post(
            outreach_emailtemplate_delete_url(template.pk), {"post": "yes"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EmailTemplate.objects.exists())

    def test_name_clash_shows_the_error_and_creates_nothing(self) -> None:
        EmailTemplateFactory(name="Welcome")

        response = self.client.post(
            outreach_emailtemplate_add_url(), {**FORM_FIELDS, "name": "WELCOME"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["adminform"].form.errors["name"],
            ["A template with this name already exists."],
        )
        self.assertEqual(EmailTemplate.objects.count(), 1)

    def test_form_has_the_rich_text_editor(self) -> None:
        response = self.client.get(outreach_emailtemplate_add_url())

        self.assertContains(response, "<trix-editor")

    def test_hostile_stored_body_is_escaped_inside_the_sample_preview(self) -> None:
        template = EmailTemplateFactory(
            body_html="<script>alert(1)</script><img src=x onerror=alert(1)>"
        )

        response = self.client.get(outreach_emailtemplate_change_url(template.pk))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<img src=x")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_sample_preview_uses_the_example_values(self) -> None:
        template = EmailTemplateFactory(
            subject="Hello {{ first_name }}", body_html="<p>Dear {{ full_name }}</p>"
        )

        response = self.client.get(outreach_emailtemplate_change_url(template.pk))

        self.assertEqual(response.context["sample_preview_subject"], "Hello Alex")
        self.assertEqual(response.context["sample_preview_html"], "<p>Dear Alex Morgan</p>")

    def test_view_permission_is_required_to_list_and_open(self) -> None:
        template = EmailTemplateFactory()
        self.client.force_login(staff_with())

        list_response = self.client.get(outreach_emailtemplate_changelist_url())
        detail_response = self.client.get(outreach_emailtemplate_change_url(template.pk))

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(detail_response.status_code, 403)

    def test_view_only_staff_can_read_but_not_write(self) -> None:
        template = EmailTemplateFactory(
            name="Original", subject="Stored subject", body_html="<p>Stored body text</p>"
        )
        self.client.force_login(staff_with("view_emailtemplate"))

        list_response = self.client.get(outreach_emailtemplate_changelist_url())
        detail_response = self.client.get(outreach_emailtemplate_change_url(template.pk))
        write_response = self.client.post(
            outreach_emailtemplate_change_url(template.pk), {**FORM_FIELDS, "name": "Hijacked"}
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Original")
        self.assertContains(detail_response, "Stored subject")
        self.assertContains(detail_response, "Stored body text")
        self.assertEqual(write_response.status_code, 403)
        template.refresh_from_db()
        self.assertEqual(template.name, "Original")

    def test_add_permission_is_required_to_add(self) -> None:
        self.client.force_login(staff_with("view_emailtemplate", "change_emailtemplate"))

        get_response = self.client.get(outreach_emailtemplate_add_url())
        post_response = self.client.post(outreach_emailtemplate_add_url(), FORM_FIELDS)

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(EmailTemplate.objects.exists())

    def test_change_permission_is_required_to_change(self) -> None:
        template = EmailTemplateFactory(name="Original")
        self.client.force_login(
            staff_with("view_emailtemplate", "add_emailtemplate", "delete_emailtemplate")
        )

        response = self.client.post(
            outreach_emailtemplate_change_url(template.pk), {**FORM_FIELDS, "name": "Changed"}
        )

        self.assertEqual(response.status_code, 403)
        template.refresh_from_db()
        self.assertEqual(template.name, "Original")

    def test_delete_permission_is_required_to_delete(self) -> None:
        template = EmailTemplateFactory()
        self.client.force_login(
            staff_with("view_emailtemplate", "add_emailtemplate", "change_emailtemplate")
        )

        response = self.client.post(
            outreach_emailtemplate_delete_url(template.pk), {"post": "yes"}
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(EmailTemplate.objects.filter(pk=template.pk).exists())

    def test_nav_entry_is_shown_only_with_the_view_permission(self) -> None:
        templates_url = outreach_emailtemplate_changelist_url()

        with_permission = inspect_page(
            self.client.get(reverse("outreach_admin:index")).content
        )
        self.client.force_login(staff_with())
        without_response = self.client.get(reverse("outreach_admin:index"))
        without_permission = inspect_page(without_response.content)

        with_links = [
            anchor.text.strip() for anchor in with_permission.find("a", href=templates_url)
        ]
        self.assertTrue(with_links)
        self.assertTrue(all(label.startswith("Templates") for label in with_links))
        self.assertEqual(without_response.status_code, 200)
        self.assertEqual(without_permission.find("a", href=templates_url), [])

    def test_sidebar_count_reflects_the_number_of_templates(self) -> None:
        EmailTemplateFactory.create_batch(3)

        response = self.client.get(outreach_emailtemplate_changelist_url())

        self.assertEqual(response.context["counts"]["email_templates"], 3)

    def test_author_is_truncated_to_the_stored_length_when_saving_in_the_admin(self) -> None:
        long_username = "u" * 240 + "@example.test"

        with patch.object(get_user_model(), "get_username", return_value=long_username):
            self.client.post(outreach_emailtemplate_add_url(), FORM_FIELDS)

        self.assertEqual(EmailTemplate.objects.get().created_by, long_username[:150])

    def test_a_name_clash_that_slips_past_validation_is_a_form_error_not_a_server_error(
        self,
    ) -> None:
        EmailTemplateFactory(name="Welcome")

        original_validate_unique = BaseModelForm.validate_unique
        skipped = []

        def skip_the_first_check(form: BaseModelForm) -> None:
            if not skipped:
                skipped.append(form)
                return
            original_validate_unique(form)

        with patch.object(BaseModelForm, "validate_unique", skip_the_first_check):
            response = self.client.post(outreach_emailtemplate_add_url(), FORM_FIELDS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["adminform"].form.errors["name"],
            ["A template with this name already exists."],
        )
        self.assertEqual(EmailTemplate.objects.count(), 1)
