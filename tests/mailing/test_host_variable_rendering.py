from outreach.models import Prospect
from tests.base import OutreachMailTagTestCase
from tests.factories import ProspectFactory


class HostVariableRenderingTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospect = ProspectFactory(first_name="Ada")

    def test_a_variable_renders_in_the_subject_the_html_and_the_text(self) -> None:
        self.register_variable(lambda prospect: "Pro", "plan_name")

        rendered = self.render_mail(
            self.prospect,
            subject="Your {{ plan_name }} plan",
            body="<p>Plan: {{ plan_name }}</p>",
        )

        self.assertEqual(rendered.subject, "Your Pro plan")
        self.assertIn("Plan: Pro", rendered.html)
        self.assertIn("Plan: Pro", rendered.text)

    def test_the_value_is_escaped_in_html_and_flattened_in_the_subject(self) -> None:
        self.register_variable(lambda prospect: "<b>Pro</b>\nPlus", "plan_name")

        rendered = self.render_mail(
            self.prospect, subject="{{ plan_name }}", body="<p>{{ plan_name }}</p>"
        )

        self.assertEqual(rendered.subject, "<b>Pro</b> Plus")
        self.assertIn("&lt;b&gt;Pro&lt;/b&gt;", rendered.html)
        self.assertNotIn("<b>Pro</b>", rendered.html)

    def test_a_value_is_never_read_again_as_a_variable_a_tag_or_a_button(self) -> None:
        self.register_echo_tag()
        self.register_variable(
            lambda prospect: (
                '{{ first_name }} {% echo "x" %} {% button "Go" "https://x.org" %}'
            ),
            "plan_name",
        )

        rendered = self.render_mail(self.prospect, body="<p>{{ plan_name }}</p>")

        self.assertIn("{{ first_name }}", rendered.html)
        self.assertIn("{% echo", rendered.html)
        self.assertEqual(self.echo_calls, [])

    def test_a_bare_word_argument_of_a_tag_and_a_button_can_name_a_variable(self) -> None:
        self.register_variable(lambda prospect: "https://example.org/offer", "offer_url")
        self.register_variable(lambda prospect: "Pro", "plan_name")
        self.register_echo_tag()

        rendered = self.render_mail(
            self.prospect,
            subject="{% echo plan_name %}",
            body='<p>{% button "See it" offer_url %}</p>',
        )

        self.assertEqual(rendered.subject, "Pro")
        self.assertIn('href="https://example.org/offer"', rendered.html)

    def test_a_variable_that_reads_the_prospect_gets_the_prospect(self) -> None:
        def greeting_name(prospect: Prospect) -> str:
            return prospect.first_name.upper()

        self.register_variable(greeting_name, "shout_name")

        rendered = self.render_mail(self.prospect, subject="{{ shout_name }}")

        self.assertEqual(rendered.subject, "ADA")
