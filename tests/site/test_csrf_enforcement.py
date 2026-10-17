from django.test import Client, override_settings

from outreach.models import Audience, EmailTemplate
from tests.base import OutreachTestCase
from tests.factories import (
    AudienceFactory,
    EmailTemplateFactory,
    ProspectFactory,
    create_outreach_staff_user,
)
from tests.routes import (
    outreach_audience_add_url,
    outreach_audience_change_url,
    outreach_audience_delete_url,
    outreach_emailtemplate_add_url,
    outreach_emailtemplate_change_url,
    outreach_emailtemplate_delete_url,
    outreach_prospect_changelist_url,
)

PERMISSIONS = [
    "view_prospect",
    "change_prospect",
    "view_emailtemplate",
    "add_emailtemplate",
    "change_emailtemplate",
    "delete_emailtemplate",
    "view_audience",
    "add_audience",
    "change_audience",
    "delete_audience",
]
TEMPLATE_FIELDS = {"name": "Welcome", "subject": "Hello", "body_html": "<p>Body</p>"}


@override_settings(OUTREACH_BASE_URL="https://outreach.example.test", OUTREACH_LANGUAGE="en")
class CsrfEnforcementTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(create_outreach_staff_user(PERMISSIONS))
        self.prospect = ProspectFactory()

    def post_compose_step(self, **fields: str) -> int:
        response = self.client.post(
            outreach_prospect_changelist_url(),
            {"action": "send_mail", "_selected_action": [str(self.prospect.pk)], **fields},
        )
        return response.status_code

    def test_every_compose_step_refuses_a_post_without_a_token(self) -> None:
        template = EmailTemplateFactory()
        steps = {
            "compose": {"step": "compose", "subject": "S", "body": "<p>B</p>"},
            "apply_template": {
                "step": "compose",
                "apply_template": "1",
                "template": str(template.pk),
            },
            "save_template": {
                "step": "save_template",
                "subject": "S",
                "body": "<p>B</p>",
                "name": "Csrf",
            },
            "preview": {"step": "preview", "subject": "S", "body": "<p>B</p>"},
            "send": {"step": "send", "subject": "S", "body": "<p>B</p>"},
        }

        for label, fields in steps.items():
            with self.subTest(step=label):
                self.assertEqual(self.post_compose_step(**fields), 403)

        self.assertEqual(EmailTemplate.objects.count(), 1)

    def test_template_admin_writes_refuse_a_post_without_a_token(self) -> None:
        template = EmailTemplateFactory(name="Original")

        add_response = self.client.post(outreach_emailtemplate_add_url(), TEMPLATE_FIELDS)
        change_response = self.client.post(
            outreach_emailtemplate_change_url(template.pk),
            {**TEMPLATE_FIELDS, "name": "Hijacked"},
        )
        delete_response = self.client.post(
            outreach_emailtemplate_delete_url(template.pk), {"post": "yes"}
        )

        self.assertEqual(
            (
                add_response.status_code,
                change_response.status_code,
                delete_response.status_code,
            ),
            (403, 403, 403),
        )
        template.refresh_from_db()
        self.assertEqual(template.name, "Original")
        self.assertEqual(EmailTemplate.objects.count(), 1)

    def test_audience_admin_writes_refuse_a_post_without_a_token(self) -> None:
        audience = AudienceFactory(name="Original")

        add_response = self.client.post(outreach_audience_add_url(), {"name": "Added"})
        change_response = self.client.post(
            outreach_audience_change_url(audience.pk), {"name": "Hijacked"}
        )
        delete_response = self.client.post(
            outreach_audience_delete_url(audience.pk), {"post": "yes"}
        )

        self.assertEqual(
            (
                add_response.status_code,
                change_response.status_code,
                delete_response.status_code,
            ),
            (403, 403, 403),
        )
        audience.refresh_from_db()
        self.assertEqual(audience.name, "Original")
        self.assertEqual(Audience.objects.count(), 1)

    def test_the_audience_actions_refuse_a_post_without_a_token(self) -> None:
        audience = AudienceFactory()

        for action in ("add_to_audience", "remove_from_audience"):
            with self.subTest(action=action):
                response = self.client.post(
                    outreach_prospect_changelist_url(),
                    {
                        "action": action,
                        "_selected_action": [str(self.prospect.pk)],
                        "apply": "1",
                        "audience": str(audience.pk),
                    },
                )
                self.assertEqual(response.status_code, 403)

        self.assertFalse(audience.prospects.exists())
