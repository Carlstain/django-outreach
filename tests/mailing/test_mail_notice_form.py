from outreach.forms import MessageForm
from tests.base import OutreachTestCase

UNSUBSCRIBE_VARIABLES = [
    "{{ unsubscribe_url }}",
    "{{unsubscribe_url}}",
    "{{  unsubscribe_url  }}",
]


class MailNoticeFormTests(OutreachTestCase):
    def build_form(
        self, body: str, *, is_newsletter: bool, header_text: str = ""
    ) -> MessageForm:
        data = {"subject": "Hello", "body": body, "header_text": header_text}
        if is_newsletter:
            data["is_newsletter"] = "on"
        return MessageForm(data=data)

    def test_a_notice_cannot_use_the_unsubscribe_variable(self) -> None:
        for variable in UNSUBSCRIBE_VARIABLES:
            with self.subTest(variable=variable):
                form = self.build_form(f"<p>Leave: {variable}</p>", is_newsletter=False)

                self.assertFalse(form.is_valid())
                self.assertIn("A notice has no unsubscribe link", form.errors["body"][0])

    def test_a_newsletter_can_use_the_unsubscribe_variable(self) -> None:
        for variable in UNSUBSCRIBE_VARIABLES:
            with self.subTest(variable=variable):
                form = self.build_form(f"<p>Leave: {variable}</p>", is_newsletter=True)

                self.assertTrue(form.is_valid(), form.errors)

    def test_a_notice_without_the_variable_is_valid(self) -> None:
        form = self.build_form("<p>New terms apply.</p>", is_newsletter=False)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data["is_newsletter"])

    def test_the_header_text_must_be_on_a_single_line(self) -> None:
        form = self.build_form("<p>Body</p>", is_newsletter=True, header_text="One\nTwo")

        self.assertFalse(form.is_valid())
        self.assertIn("single line", form.errors["header_text"][0])

    def test_the_header_text_is_stripped(self) -> None:
        form = self.build_form("<p>Body</p>", is_newsletter=True, header_text="  Club  ")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["header_text"], "Club")
