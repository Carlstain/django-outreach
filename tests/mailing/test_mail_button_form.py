from outreach.forms import MessageForm
from tests.base import OutreachMailTagTestCase


class MailButtonFormTests(OutreachMailTagTestCase):
    def build_form(self, subject: str = "Hello", body: str = "<p>Body</p>") -> MessageForm:
        return MessageForm(data={"subject": subject, "body": body})

    def test_valid_buttons_are_accepted(self) -> None:
        self.register_tag(lambda prospect: "https://example.org", "booking_url")
        bodies = {
            "literal": '<p>{% button "Go" "https://example.org" %}</p>',
            "mailto": '<p>{% button "Write" "mailto:team@example.org" %}</p>',
            "variable": '<p>{% button "Leave" unsubscribe_url %}</p>',
            "tag": '<p>{% button "Book" booking_url %}</p>',
        }
        for name, body in bodies.items():
            with self.subTest(link=name):
                form = self.build_form(body=body)

                self.assertTrue(form.is_valid(), form.errors)

    def test_a_button_in_the_subject_is_rejected(self) -> None:
        form = self.build_form(subject='{% button "Go" "https://example.org" %}')

        self.assertFalse(form.is_valid())
        self.assertIn("only be used in the message body", form.errors["subject"][0])

    def test_an_invalid_button_is_rejected(self) -> None:
        bodies = {
            "label only": '<p>{% button "Go" %}</p>',
            "too many arguments": '<p>{% button "Go" "https://example.org" "extra" %}</p>',
            "empty label": '<p>{% button "" "https://example.org" %}</p>',
            "javascript link": '<p>{% button "Go" "javascript:alert(1)" %}</p>',
            "relative link": '<p>{% button "Go" "/relative" %}</p>',
            "empty link": '<p>{% button "Go" "" %}</p>',
        }
        for name, body in bodies.items():
            with self.subTest(case=name):
                form = self.build_form(body=body)

                self.assertFalse(form.is_valid())
                self.assertIn("Invalid button", form.errors["body"][0])

    def test_an_unknown_bare_word_as_the_link_is_rejected(self) -> None:
        form = self.build_form(body='<p>{% button "Go" nope %}</p>')

        self.assertFalse(form.is_valid())
        self.assertIn("Unknown variable(s): nope", form.errors["body"][0])
