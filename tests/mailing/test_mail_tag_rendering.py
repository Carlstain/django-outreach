from tests.base import OutreachMailTagTestCase
from tests.factories import ProspectFactory


class MailTagRenderingTests(OutreachMailTagTestCase):
    def test_the_output_is_escaped_in_the_html(self) -> None:
        self.register_tag(lambda prospect: "<b>bold</b> & more", "markup")

        rendered = self.render_mail(ProspectFactory(), body="<p>{% markup %}</p>")

        self.assertIn("&lt;b&gt;bold&lt;/b&gt; &amp; more", rendered.html)
        self.assertNotIn("<b>bold</b>", rendered.html)

    def test_newlines_are_collapsed_in_the_subject(self) -> None:
        self.register_tag(lambda prospect: "first\nsecond\r\nthird", "lines")

        rendered = self.render_mail(ProspectFactory(), subject="Hi {% lines %}")

        self.assertEqual(rendered.subject, "Hi first second  third")

    def test_quoted_arguments_are_passed_with_either_quote_style(self) -> None:
        self.register_echo_tag()

        self.render_mail(ProspectFactory(), body="<p>{% echo \"double\" 'single' %}</p>")

        self.assertEqual(self.echo_calls, [("double", "single")])

    def test_html_entities_in_an_argument_are_unescaped(self) -> None:
        self.register_echo_tag()

        rendered = self.render_mail(
            ProspectFactory(), body='<p>{% echo "Tom &amp; Jerry" %}</p>'
        )

        self.assertEqual(self.echo_calls, [("Tom & Jerry",)])
        self.assertIn("Tom &amp; Jerry", rendered.html)

    def test_the_prospect_is_the_first_input(self) -> None:
        prospect = ProspectFactory(email="given@test.com")
        self.register_tag(lambda received_prospect: received_prospect.email, "who")

        rendered = self.render_mail(prospect, subject="{% who %}")

        self.assertEqual(rendered.subject, "given@test.com")

    def test_an_unknown_tag_is_left_as_written(self) -> None:
        rendered = self.render_mail(ProspectFactory(), body="<p>{% nope %}</p>")

        self.assertIn("{% nope %}", rendered.html)

    def test_tag_syntax_inside_prospect_data_is_not_run(self) -> None:
        self.register_echo_tag()
        prospect = ProspectFactory(first_name='{% echo "injected" %}')

        rendered = self.render_mail(
            prospect, subject="{{ first_name }}", body="<p>{{ first_name }}</p>"
        )

        self.assertEqual(self.echo_calls, [])
        self.assertEqual(rendered.subject, '{% echo "injected" %}')
        self.assertIn('{% echo "injected" %}', rendered.text)
