from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.messages import ERROR, SUCCESS, get_messages
from django.core import mail
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.test import override_settings

from outreach.models import EmailTemplate
from tests.base import OutreachTestCase
from tests.factories import EmailTemplateFactory, ProspectFactory, create_outreach_staff_user
from tests.html_inspector import inspect_page
from tests.routes import outreach_prospect_changelist_url

BASE_PERMISSIONS = ["view_prospect", "change_prospect"]
FULL_PERMISSIONS = [
    *BASE_PERMISSIONS,
    "view_emailtemplate",
    "add_emailtemplate",
    "change_emailtemplate",
]
POSTED_SUBJECT = "Posted subject"
POSTED_BODY = "<p>Posted body</p>"


def flashed(response: HttpResponse) -> list[tuple[int, str]]:
    return [
        (message.level, message.message) for message in get_messages(response.wsgi_request)
    ]


@override_settings(OUTREACH_BASE_URL="https://outreach.example.test", OUTREACH_LANGUAGE="en")
class ComposeTemplatesTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = create_outreach_staff_user(FULL_PERMISSIONS)
        self.client.force_login(self.staff_user)
        self.prospects = [
            ProspectFactory(first_name="Alice"),
            ProspectFactory(first_name="Bruno"),
        ]

    def post_step(self, step: str | None = None, **fields: str) -> HttpResponse:
        data = {
            "action": "send_mail",
            "_selected_action": [str(prospect.pk) for prospect in self.prospects],
            **fields,
        }
        if step is not None:
            data["step"] = step
        return self.client.post(outreach_prospect_changelist_url(), data)

    def test_picker_lists_templates_for_users_who_may_view_them(self) -> None:
        second = EmailTemplateFactory(name="Second")
        first = EmailTemplateFactory(name="First")

        response = self.post_step()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["email_templates"]),
            [(str(first.pk), "First"), (str(second.pk), "Second")],
        )

    def test_picker_is_empty_for_users_who_may_not_view_templates(self) -> None:
        EmailTemplateFactory()
        self.client.force_login(create_outreach_staff_user(BASE_PERMISSIONS))

        response = self.post_step()

        self.assertEqual(list(response.context["email_templates"]), [])

    def test_use_template_fills_subject_and_body_and_flags_the_notice(self) -> None:
        template = EmailTemplateFactory(
            subject="Template subject", body_html="<p>Template body</p>"
        )

        response = self.post_step("compose", apply_template="1", template=str(template.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["subject"].value(), "Template subject")
        self.assertEqual(response.context["form"]["body"].value(), "<p>Template body</p>")
        self.assertTrue(response.context["template_applied"])
        self.assertEqual(response.context["selected_template"], template)

    def test_missing_or_malformed_template_keeps_the_posted_text(self) -> None:
        for template_value in (str(uuid4()), "not-a-uuid", ""):
            with self.subTest(template=template_value):
                response = self.post_step(
                    "compose",
                    apply_template="1",
                    template=template_value,
                    subject=POSTED_SUBJECT,
                    body=POSTED_BODY,
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    flashed(response), [(ERROR, "That template is not available.")]
                )
                self.assertEqual(response.context["form"]["subject"].value(), POSTED_SUBJECT)
                self.assertEqual(response.context["form"]["body"].value(), POSTED_BODY)
                self.assertFalse(response.context["template_applied"])
                self.assertIsNone(response.context["selected_template"])

    def test_editing_the_message_after_preview_does_not_apply_a_template(self) -> None:
        EmailTemplateFactory()

        response = self.post_step(
            "compose", subject=POSTED_SUBJECT, body=POSTED_BODY, template=str(uuid4())
        )

        self.assertFalse(response.context["template_applied"])
        self.assertEqual(response.context["form"]["subject"].value(), POSTED_SUBJECT)
        self.assertEqual(flashed(response), [])

    def test_save_as_template_creates_it_and_selects_it(self) -> None:
        response = self.post_step(
            "save_template",
            subject="Hello {{ first_name }}",
            body="<p>Hi {{ first_name }}</p><script>alert(1)</script>",
            name="  Welcome  ",
        )

        template = EmailTemplate.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            (template.name, template.subject, template.body_html, template.created_by),
            (
                "Welcome",
                "Hello {{ first_name }}",
                "<p>Hi {{ first_name }}</p>",
                self.staff_user.get_username(),
            ),
        )
        self.assertEqual(flashed(response), [(SUCCESS, "Template saved.")])
        self.assertEqual(response.context["selected_template"], template)

    def test_name_clash_without_overwrite_is_a_field_error(self) -> None:
        existing = EmailTemplateFactory(name="Welcome", subject="Old subject")

        response = self.post_step(
            "save_template", subject=POSTED_SUBJECT, body=POSTED_BODY, name="welcome"
        )

        self.assertEqual(
            response.context["save_template_form"].errors["name"],
            ["A template named “welcome” already exists. Tick the box to replace it."],
        )
        existing.refresh_from_db()
        self.assertEqual(existing.subject, "Old subject")
        self.assertEqual(EmailTemplate.objects.count(), 1)

    def test_name_clash_for_a_user_who_cannot_replace_has_no_replace_advice(self) -> None:
        EmailTemplateFactory(name="Welcome", subject="Old subject")
        self.client.force_login(
            create_outreach_staff_user(
                [*BASE_PERMISSIONS, "view_emailtemplate", "add_emailtemplate"]
            )
        )

        response = self.post_step(
            "save_template", subject=POSTED_SUBJECT, body=POSTED_BODY, name="welcome"
        )

        self.assertEqual(
            response.context["save_template_form"].errors["name"],
            ["A template named “welcome” already exists."],
        )

    def test_forged_template_id_from_a_user_who_may_not_view_templates_is_refused(
        self,
    ) -> None:
        template = EmailTemplateFactory(subject="Secret subject")
        self.client.force_login(create_outreach_staff_user(BASE_PERMISSIONS))

        response = self.post_step(
            "compose",
            apply_template="1",
            template=str(template.pk),
            subject=POSTED_SUBJECT,
            body=POSTED_BODY,
        )

        self.assertEqual(flashed(response), [(ERROR, "That template is not available.")])
        self.assertFalse(response.context["template_applied"])
        self.assertEqual(response.context["form"]["subject"].value(), POSTED_SUBJECT)
        self.assertNotContains(response, "Secret subject")

    def test_overwrite_replaces_the_content_and_keeps_the_author(self) -> None:
        existing = EmailTemplateFactory(name="Welcome", created_by="original-author")

        response = self.post_step(
            "save_template",
            subject=POSTED_SUBJECT,
            body=POSTED_BODY,
            name="WELCOME",
            overwrite="on",
        )

        existing.refresh_from_db()
        self.assertEqual(flashed(response), [(SUCCESS, "Template saved.")])
        self.assertEqual(EmailTemplate.objects.count(), 1)
        self.assertEqual(
            (existing.subject, existing.body_html, existing.created_by),
            (POSTED_SUBJECT, POSTED_BODY, "original-author"),
        )

    def test_overwrite_needs_the_change_permission(self) -> None:
        existing = EmailTemplateFactory(name="Welcome", subject="Old subject")
        self.client.force_login(
            create_outreach_staff_user(
                [*BASE_PERMISSIONS, "view_emailtemplate", "add_emailtemplate"]
            )
        )

        response = self.post_step(
            "save_template",
            subject=POSTED_SUBJECT,
            body=POSTED_BODY,
            name="Welcome",
            overwrite="on",
        )

        existing.refresh_from_db()
        self.assertEqual(flashed(response), [(ERROR, "You may not replace templates.")])
        self.assertEqual(existing.subject, "Old subject")

    def test_saving_needs_the_add_permission(self) -> None:
        self.client.force_login(
            create_outreach_staff_user([*BASE_PERMISSIONS, "view_emailtemplate"])
        )

        response = self.post_step(
            "save_template", subject=POSTED_SUBJECT, body=POSTED_BODY, name="Welcome"
        )

        self.assertEqual(flashed(response), [(ERROR, "You may not add templates.")])
        self.assertFalse(EmailTemplate.objects.exists())

    def test_selected_prospects_and_select_across_survive_every_step(self) -> None:
        template = EmailTemplateFactory()
        extra_prospects = [ProspectFactory() for _ in range(2)]
        selected_pks = [str(self.prospects[0].pk)]
        steps = {
            "apply": {"step": "compose", "apply_template": "1", "template": str(template.pk)},
            "save": {
                "step": "save_template",
                "subject": POSTED_SUBJECT,
                "body": POSTED_BODY,
                "name": "Carried",
            },
            "preview": {"step": "preview", "subject": POSTED_SUBJECT, "body": POSTED_BODY},
        }

        for label, fields in steps.items():
            with self.subTest(step=label):
                response = self.client.post(
                    outreach_prospect_changelist_url(),
                    {
                        "action": "send_mail",
                        "_selected_action": selected_pks,
                        "select_across": "1",
                        **fields,
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["queryset_ids"], selected_pks)
                self.assertEqual(response.context["select_across"], 1)
                self.assertEqual(
                    len(response.context["plan"].recipients),
                    len(self.prospects) + len(extra_prospects),
                )

    def test_template_fields_are_not_carried_into_the_preview(self) -> None:
        template = EmailTemplateFactory()

        response = self.post_step(
            "preview",
            subject=POSTED_SUBJECT,
            body=POSTED_BODY,
            template=str(template.pk),
            apply_template="1",
            name="Leftover",
            overwrite="on",
        )

        self.assertEqual(response.status_code, 200)
        for field_name in ("template", "apply_template", "name", "overwrite"):
            self.assertNotContains(response, f'name="{field_name}"')

    def test_message_sent_after_using_a_template_carries_its_body_to_each_recipient(
        self,
    ) -> None:
        template = EmailTemplateFactory(
            subject="Hello {{ first_name }}",
            body_html="<p>Dear {{ first_name }}, welcome.</p>",
        )
        applied = self.post_step("compose", apply_template="1", template=str(template.pk))

        self.post_step(
            "send",
            subject=applied.context["form"]["subject"].value(),
            body=applied.context["form"]["body"].value(),
        )

        by_address = {message.to[0]: message for message in mail.outbox}
        for prospect in self.prospects:
            message = by_address[prospect.email]
            self.assertEqual(message.subject, f"Hello {prospect.first_name}")
            self.assertIn(f"Dear {prospect.first_name}, welcome.", message.body)
            self.assertIn(f"Dear {prospect.first_name}, welcome.", message.alternatives[0][0])

    def test_save_block_does_not_block_the_other_buttons_with_browser_validation(self) -> None:
        response = self.post_step()

        page = inspect_page(response.content)
        name_inputs = page.find("input", name="name")
        self.assertEqual(len(name_inputs), 1)
        self.assertNotIn("required", name_inputs[0].attributes)
        form_buttons = page.submit_buttons_in_form(name_inputs[0].form_index)
        self.assertEqual(form_buttons[0].attributes.get("name"), "step")
        self.assertEqual(form_buttons[0].attributes.get("value"), "preview")
        for preview_button in page.find("button", name="step", value="preview"):
            self.assertIn("formnovalidate", preview_button.attributes)
        apply_buttons = page.find("button", name="apply_template")
        save_buttons = page.find("button", name="step", value="save_template")
        self.assertEqual(len(apply_buttons), 1)
        self.assertEqual(len(save_buttons), 1)
        self.assertIn("formnovalidate", apply_buttons[0].attributes)
        self.assertIn("formnovalidate", save_buttons[0].attributes)

    def test_author_is_truncated_to_the_stored_length_when_saving_from_compose(self) -> None:
        long_username = "u" * 240 + "@example.test"

        with patch.object(get_user_model(), "get_username", return_value=long_username):
            self.post_step(
                "save_template", subject=POSTED_SUBJECT, body=POSTED_BODY, name="Long"
            )

        self.assertEqual(EmailTemplate.objects.get().created_by, long_username[:150])

    def test_a_name_taken_after_the_lookup_is_a_field_error_not_a_server_error(self) -> None:
        EmailTemplateFactory(name="Welcome")

        with patch.object(QuerySet, "first", return_value=None):
            response = self.post_step(
                "save_template", subject=POSTED_SUBJECT, body=POSTED_BODY, name="welcome"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["save_template_form"].errors["name"],
            ["A template named “welcome” already exists. Tick the box to replace it."],
        )
        self.assertEqual(EmailTemplate.objects.count(), 1)
