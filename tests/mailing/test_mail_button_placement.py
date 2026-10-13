from outreach.forms import MessageForm
from outreach.services.mail_buttons import InvalidButtonLink
from tests.base import OutreachMailTagTestCase
from tests.factories import ProspectFactory

HOSTILE_LINK = "mailto:team@example.org onmouseover=alert(1)//"


class MailButtonPlacementTests(OutreachMailTagTestCase):
    def build_form(self, body: str) -> MessageForm:
        return MessageForm(data={"subject": "Hello", "body": body})

    def test_a_button_inside_an_attribute_is_rejected_by_the_form(self) -> None:
        form = self.build_form('<p><a href="{% button organization organization %}">x</a></p>')

        self.assertFalse(form.is_valid())
        self.assertIn("cannot be placed inside", form.errors["body"][0])

    def test_a_button_hidden_behind_a_closing_bracket_is_rejected_by_the_form(self) -> None:
        form = self.build_form('<p><a href="{% button "x>" organization %}">x</a></p>')

        self.assertFalse(form.is_valid())

    def test_a_button_inside_an_attribute_never_reaches_the_sent_mail(self) -> None:
        prospect = ProspectFactory(organization=HOSTILE_LINK)
        body = '<p><a href="{% button organization organization %}">x</a></p>'

        for preview in (False, True):
            with self.subTest(preview=preview), self.assertRaises(InvalidButtonLink):
                self.render_mail(prospect, body=body, preview=preview)

    def test_a_link_with_a_space_or_without_a_host_is_rejected_by_the_form(self) -> None:
        bodies = {
            "space in a web link": '<p>{% button "Go" "https://example.org/a b" %}</p>',
            "space in a mailto link": f'<p>{{% button "Go" "{HOSTILE_LINK}" %}}</p>',
            "web link without a host": '<p>{% button "Go" "https://" %}</p>',
        }
        for name, body in bodies.items():
            with self.subTest(case=name):
                form = self.build_form(body)

                self.assertFalse(form.is_valid())
                self.assertIn("Invalid button", form.errors["body"][0])

    def test_a_prospect_value_with_a_space_cannot_be_the_link(self) -> None:
        prospect = ProspectFactory(organization=HOSTILE_LINK)

        with self.assertRaises(InvalidButtonLink):
            self.render_mail(prospect, body='<p>{% button "Go" organization %}</p>')
