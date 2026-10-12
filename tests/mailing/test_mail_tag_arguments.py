from tests.base import OutreachMailTagTestCase
from tests.factories import ProspectFactory


class MailTagArgumentsTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.register_echo_tag()

    def test_a_bare_word_passes_the_raw_value_of_the_variable(self) -> None:
        prospect = ProspectFactory(first_name="Ada & <b>")

        self.render_mail(prospect, body="<p>{% echo first_name %}</p>")

        self.assertEqual(self.echo_calls, [("Ada & <b>",)])

    def test_the_value_is_escaped_exactly_once_in_the_html(self) -> None:
        prospect = ProspectFactory(first_name="Ada & <b>")

        rendered = self.render_mail(prospect, body="<p>{% echo first_name %}</p>")

        self.assertIn("Ada &amp; &lt;b&gt;", rendered.html)
        self.assertNotIn("&amp;amp;", rendered.html)
        self.assertIn("Ada & <b>", rendered.text)

    def test_a_variable_and_a_literal_can_be_mixed(self) -> None:
        prospect = ProspectFactory(first_name="Ada", last_name="Lovelace")

        rendered = self.render_mail(prospect, subject='{% echo first_name "and" last_name %}')

        self.assertEqual(rendered.subject, "Ada and Lovelace")
        self.assertEqual(self.echo_calls, [("Ada", "and", "Lovelace")])

    def test_an_empty_variable_is_passed_as_an_empty_string(self) -> None:
        prospect = ProspectFactory(organization="")

        self.render_mail(prospect, subject="{% echo organization %}")

        self.assertEqual(self.echo_calls, [("",)])

    def test_the_unsubscribe_url_is_available_as_an_argument(self) -> None:
        prospect = ProspectFactory()

        rendered = self.render_mail(prospect, subject="{% echo unsubscribe_url %}")

        self.assertTrue(rendered.subject.startswith("https://outreach.example.test/"))

    def test_a_bare_word_naming_a_tag_passes_the_output_of_that_tag(self) -> None:
        self.register_tag(lambda prospect: "LOUD", "shout")

        rendered = self.render_mail(ProspectFactory(), subject="{% echo shout %}")

        self.assertEqual(rendered.subject, "LOUD")
        self.assertEqual(self.echo_calls, [("LOUD",)])

    def test_a_tag_named_by_a_bare_word_receives_only_the_prospect(self) -> None:
        received_arguments: list[tuple[str, ...]] = []

        def inspector(prospect: object, *arguments: str) -> str:
            received_arguments.append(arguments)
            return "seen"

        self.register_tag(inspector, "inspector")

        self.render_mail(ProspectFactory(), subject="{% echo inspector %}")

        self.assertEqual(received_arguments, [()])

    def test_an_unknown_bare_word_is_passed_as_an_empty_string(self) -> None:
        self.render_mail(ProspectFactory(), subject="{% echo nothing_by_that_name %}")

        self.assertEqual(self.echo_calls, [("",)])
