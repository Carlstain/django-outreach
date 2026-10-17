from django.http import HttpResponse
from django.test import override_settings

from outreach.models import EmailTemplate, Mailing
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.email_templates.test_compose_templates import FULL_PERMISSIONS
from tests.factories import (
    EmailTemplateFactory,
    ProspectFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_prospect_changelist_url


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL,
    OUTREACH_LANGUAGE="en",
    OUTREACH_MAIL_LANGUAGE="fr",
)
class ComposeLanguageTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user(FULL_PERMISSIONS))
        self.prospect = ProspectFactory()

    def post_step(self, step: str | None = None, **fields: str) -> HttpResponse:
        data = {
            "action": "send_mail",
            "_selected_action": [str(self.prospect.pk)],
            "is_newsletter": "on",
            **fields,
        }
        if step is not None:
            data["step"] = step
        return self.client.post(outreach_prospect_changelist_url(), data)

    def test_the_language_starts_on_the_mail_default_whatever_the_interface_cookie(
        self,
    ) -> None:
        self.client.cookies["outreach_language"] = "es"

        response = self.post_step()

        self.assertEqual(response.context["form"]["language"].value(), "fr")

    def test_the_chosen_language_is_stored_on_the_mailing(self) -> None:
        response = self.post_step("send", subject="S", body="<p>B</p>", language="es")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Mailing.objects.get().language, "es")

    def test_the_preview_names_the_language(self) -> None:
        response = self.post_step("preview", subject="S", body="<p>B</p>", language="pt-br")

        self.assertContains(response, "Português (Brasil)")

    def test_applying_a_template_fills_in_its_language(self) -> None:
        template = EmailTemplateFactory(language="es")

        response = self.post_step("compose", apply_template="1", template=str(template.pk))

        self.assertEqual(response.context["form"]["language"].value(), "es")

    def test_applying_a_template_with_no_language_uses_the_mail_default(self) -> None:
        template = EmailTemplateFactory(language="")

        response = self.post_step("compose", apply_template="1", template=str(template.pk))

        self.assertEqual(response.context["form"]["language"].value(), "fr")

    def test_saving_a_template_keeps_the_language(self) -> None:
        self.post_step(
            "save_template",
            subject="S",
            body="<p>B</p>",
            language="pt",
            name="Portuguese welcome",
        )

        self.assertEqual(EmailTemplate.objects.get().language, "pt")
