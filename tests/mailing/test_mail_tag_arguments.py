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
