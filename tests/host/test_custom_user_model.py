from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings

from outreach.models import Prospect
from outreach.services.variables import MailVariables
from tests.accounts.factories import EmailUserFactory
from tests.base import OutreachTestCase
from tests.factories import EmailTemplateFactory, ProspectFactory, create_outreach_staff_user
from tests.routes import (
    outreach_emailtemplate_add_url,
    outreach_emailtemplate_change_url,
    outreach_emailtemplate_changelist_url,
    outreach_help_url,
    outreach_index_url,
    outreach_prospect_changelist_url,
)


class CustomUserModelTests(OutreachTestCase):
    def test_the_test_project_runs_with_the_email_user_model(self) -> None:
        self.assertEqual(get_user_model()._meta.label, "accounts.EmailUser")
        self.assertIs(Prospect._meta.get_field("user").related_model, get_user_model())

    def test_all_migrations_are_applied(self) -> None:
        executor = MigrationExecutor(connection)

        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())

        self.assertEqual(pending, [])

    def test_prospect_links_to_the_user_by_the_email_field_ignoring_case(self) -> None:
        user = EmailUserFactory(email="Jane@Test.com")

        prospect = ProspectFactory(email="jane@test.com")

        self.assertEqual(prospect.user, user)

    def test_prospect_is_not_linked_when_no_user_has_the_email(self) -> None:
        EmailUserFactory(email="someone.else@test.com")

        prospect = ProspectFactory(email="jane@test.com")

        self.assertIsNone(prospect.user)

    def test_linked_user_without_name_fields_gives_empty_names(self) -> None:
        user = EmailUserFactory(email="jane@test.com")
        prospect = ProspectFactory(email="jane@test.com", first_name="", last_name="")

        values = MailVariables().values_for(prospect)

        self.assertEqual(prospect.user, user)
        self.assertEqual(
            values,
            {
                "first_name": "",
                "last_name": "",
                "full_name": "",
                "organization": "",
                "email": "jane@test.com",
                "city": "",
                "country": "",
            },
        )

    def test_load_users_command_works_without_name_fields(self) -> None:
        user = EmailUserFactory(email="Jane@Test.com")

        call_command("outreach_load_users")

        prospect = Prospect.objects.get()
        self.assertEqual(prospect.user, user)
        self.assertEqual((prospect.first_name, prospect.last_name), ("", ""))

    def test_staff_with_permissions_can_use_the_admin_site(self) -> None:
        staff_user = create_outreach_staff_user(user_factory=EmailUserFactory)
        self.client.force_login(staff_user)

        for page_url in (
            outreach_index_url(),
            outreach_help_url(),
            outreach_prospect_changelist_url(),
        ):
            with self.subTest(page_url=page_url):
                self.assertEqual(self.client.get(page_url).status_code, 200)

    def test_staff_without_permissions_is_sent_to_login(self) -> None:
        staff_user = create_outreach_staff_user(
            permission_codenames=[], user_factory=EmailUserFactory
        )
        self.client.force_login(staff_user)

        response = self.client.get(outreach_prospect_changelist_url())

        self.assertEqual(response.status_code, 302)

    @override_settings(
        OUTREACH_BASE_URL="https://outreach.example.test", OUTREACH_LANGUAGE="en"
    )
    def test_mail_to_a_linked_user_without_names_uses_the_fallback(self) -> None:
        staff_user = create_outreach_staff_user(user_factory=EmailUserFactory)
        self.client.force_login(staff_user)
        EmailUserFactory(email="jane@test.com")
        prospect = ProspectFactory(email="jane@test.com", first_name="", last_name="")

        self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [str(prospect.pk)],
                "step": "send",
                "subject": "Hi {{ first_name | there }}",
                "body": "<p>Body</p>",
            },
        )

        self.assertEqual([message.subject for message in mail.outbox], ["Hi there"])

    def test_template_pages_and_the_compose_picker_render_for_a_user_without_names(
        self,
    ) -> None:
        staff_user = create_outreach_staff_user(
            [
                "view_prospect",
                "change_prospect",
                "view_emailtemplate",
                "add_emailtemplate",
                "change_emailtemplate",
            ],
            user_factory=EmailUserFactory,
        )
        self.client.force_login(staff_user)
        template = EmailTemplateFactory(name="Welcome")
        prospect = ProspectFactory()

        for page_url in (
            outreach_emailtemplate_changelist_url(),
            outreach_emailtemplate_add_url(),
            outreach_emailtemplate_change_url(template.pk),
        ):
            with self.subTest(page_url=page_url):
                self.assertEqual(self.client.get(page_url).status_code, 200)
        compose_response = self.client.post(
            outreach_prospect_changelist_url(),
            {"action": "send_mail", "_selected_action": [str(prospect.pk)]},
        )
        self.assertEqual(compose_response.status_code, 200)
        self.assertEqual(
            list(compose_response.context["email_templates"]), [(str(template.pk), "Welcome")]
        )
