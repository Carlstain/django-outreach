from outreach.conf import outreach_settings
from tests.base import OutreachMailTagTestCase
from tests.factories import ProspectFactory

BUTTON_STYLE_MARKER = "display: inline-block"


class MailButtonRenderingTests(OutreachMailTagTestCase):
    def test_a_literal_link_renders_a_styled_anchor_with_the_theme_colours(self) -> None:
        colors = outreach_settings.theme.email

        rendered = self.render_mail(
            ProspectFactory(),
            body='<p>{% button "Read more" "https://example.org/a?b=1&c=2" %}</p>',
        )

        self.assertIn('href="https://example.org/a?b=1&amp;c=2"', rendered.html)
        self.assertIn(f"background-color: {colors.accent}", rendered.html)
        self.assertIn(f"color: {colors.on_accent}", rendered.html)
        self.assertIn('rel="noopener noreferrer">Read more</a>', rendered.html)

    def test_the_label_is_escaped(self) -> None:
        prospect = ProspectFactory(first_name="<b>Tom</b> & Jerry")

        rendered = self.render_mail(
            prospect, body='<p>{% button first_name "https://example.org" %}</p>'
        )

        self.assertIn(">&lt;b&gt;Tom&lt;/b&gt; &amp; Jerry</a>", rendered.html)
        self.assertNotIn("<b>Tom</b>", rendered.html)

    def test_a_variable_can_be_the_link(self) -> None:
        rendered = self.render_mail(
            ProspectFactory(), body='<p>{% button "Leave" unsubscribe_url %}</p>'
        )

        self.assertIn('href="https://outreach.example.test/', rendered.html)
        self.assertIn(">Leave</a>", rendered.html)

    def test_a_variable_can_be_the_label(self) -> None:
        rendered = self.render_mail(
            ProspectFactory(first_name="Ada"),
            body='<p>{% button first_name "https://example.org" %}</p>',
        )

        self.assertIn(">Ada</a>", rendered.html)

    def test_a_tag_can_be_the_link(self) -> None:
        self.register_tag(lambda prospect: "https://example.org/book", "booking_url")

        rendered = self.render_mail(
            ProspectFactory(), body='<p>{% button "Book" booking_url %}</p>'
        )

        self.assertIn('href="https://example.org/book"', rendered.html)

    def test_the_text_part_shows_the_label_and_the_link(self) -> None:
        rendered = self.render_mail(
            ProspectFactory(), body='<p>{% button "Read more" "https://example.org/a" %}</p>'
        )

        self.assertIn("Read more (https://example.org/a)", rendered.text)

    def test_a_mailto_link_is_accepted(self) -> None:
        rendered = self.render_mail(
            ProspectFactory(), body='<p>{% button "Write" "mailto:team@example.org" %}</p>'
        )

        self.assertIn('href="mailto:team@example.org"', rendered.html)

    def test_button_syntax_inside_prospect_data_is_not_turned_into_a_button(self) -> None:
        prospect = ProspectFactory(first_name="{% button city unsubscribe_url %}")

        rendered = self.render_mail(prospect, body="<p>{{ first_name }}</p>")

        self.assertNotIn(BUTTON_STYLE_MARKER, rendered.html)
        self.assertIn("{% button city unsubscribe_url %}", rendered.text)

    def test_a_forged_token_in_prospect_data_stays_text(self) -> None:
        forged_token = f"outreach-button-{'0' * 32}-0"
        prospect = ProspectFactory(first_name=forged_token)

        rendered = self.render_mail(
            prospect, body='<p>{{ first_name }} {% button "Real" "https://example.org" %}</p>'
        )

        self.assertIn(forged_token, rendered.text)
        self.assertEqual(rendered.html.count(BUTTON_STYLE_MARKER), 1)
