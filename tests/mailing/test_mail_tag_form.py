from outreach.forms import MessageForm
from tests.base import OutreachMailTagTestCase


class MailTagFormTests(OutreachMailTagTestCase):
    def build_form(self, subject: str = "Hello", body: str = "<p>Body</p>") -> MessageForm:
        return MessageForm(data={"subject": subject, "body": body})

    def test_valid_tags_are_accepted_in_subject_and_body(self) -> None:
        form = self.build_form(
            subject="{% greeting %}",
            body='<p>{% today "j F Y" %} {% member_since %}</p>',
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_an_unknown_tag_is_rejected(self) -> None:
        for field, form in {
            "body": self.build_form(body="<p>{% nope %}</p>"),
            "subject": self.build_form(subject="{% nope %}"),
        }.items():
            with self.subTest(field=field):
                self.assertFalse(form.is_valid())
                self.assertIn("Unknown tag(s): nope", form.errors[field][0])

    def test_too_many_arguments_are_rejected(self) -> None:
        form = self.build_form(body='<p>{% greeting "extra" %}</p>')

        self.assertFalse(form.is_valid())
        self.assertIn("Invalid arguments for tag(s): greeting", form.errors["body"][0])

    def test_an_argument_over_the_length_cap_is_rejected(self) -> None:
        long_argument = "x" * 201
        form = self.build_form(body=f'<p>{{% today "{long_argument}" %}}</p>')

        self.assertFalse(form.is_valid())
        self.assertIn("Invalid arguments for tag(s): today", form.errors["body"][0])

    def test_an_unknown_variable_used_as_an_argument_is_rejected(self) -> None:
        form = self.build_form(body="<p>{% today nope %}</p>")

        self.assertFalse(form.is_valid())
        self.assertIn("Unknown variable(s): nope", form.errors["body"][0])

    def test_a_known_variable_used_as_an_argument_is_accepted(self) -> None:
        form = self.build_form(body="<p>{% today first_name %}</p>")

        self.assertTrue(form.is_valid(), form.errors)

    def test_a_stray_delimiter_is_rejected(self) -> None:
        for body in ("<p>{% greeting</p>", "<p>greeting %}</p>"):
            with self.subTest(body=body):
                form = self.build_form(body=body)

                self.assertFalse(form.is_valid())
                self.assertIn("Malformed tag", form.errors["body"][0])
