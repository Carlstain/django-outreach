from django.test import override_settings

from outreach.models import Prospect
from tests.base import MAIL_BASE_URL, OutreachMailTagTestCase
from tests.factories import (
    OUTREACH_PROSPECT_PERMISSIONS,
    ProspectFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_prospect_changelist_url


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class MailTagRenderModeTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.preview_values: list[bool] = []

        def probe(prospect: Prospect, *, preview: bool = False) -> str:
            self.preview_values.append(preview)
            return "previewing" if preview else "sending"

        self.register_tag(probe, "probe")

    def post_compose_step(self, prospect: Prospect, step: str, body: str) -> object:
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [str(prospect.pk)],
                "step": step,
                "subject": "Hello",
                "body": body,
            },
        )

    def test_a_tag_declaring_preview_gets_false_in_a_normal_render(self) -> None:
        rendered = self.render_mail(ProspectFactory(), subject="{% probe %}")

        self.assertEqual(rendered.subject, "sending")
        self.assertEqual(self.preview_values, [False])

    def test_a_tag_declaring_preview_gets_true_when_previewing(self) -> None:
        rendered = self.render_mail(ProspectFactory(), subject="{% probe %}", preview=True)

        self.assertEqual(rendered.subject, "previewing")
        self.assertEqual(self.preview_values, [True])

    def test_the_compose_preview_passes_true_and_the_send_step_passes_false(self) -> None:
        self.client.force_login(create_outreach_staff_user(OUTREACH_PROSPECT_PERMISSIONS))
        prospect = ProspectFactory()
        body = "<p>{% probe %}</p>"

        self.post_compose_step(prospect, "preview", body)
        values_after_preview = list(self.preview_values)
        self.post_compose_step(prospect, "send", body)

        self.assertEqual(values_after_preview, [True])
        self.assertEqual(self.preview_values, [True, False])

    def test_a_tag_without_the_parameter_is_called_as_before(self) -> None:
        self.register_tag(lambda prospect: "plain", "plain")

        rendered = self.render_mail(ProspectFactory(), subject="{% plain %}", preview=True)

        self.assertEqual(rendered.subject, "plain")

    def test_the_flag_reaches_a_tag_named_as_a_bare_word_argument(self) -> None:
        self.register_echo_tag()

        self.render_mail(ProspectFactory(), subject="{% echo probe %}", preview=True)

        self.assertEqual(self.echo_calls, [("previewing",)])
        self.assertEqual(self.preview_values, [True])
