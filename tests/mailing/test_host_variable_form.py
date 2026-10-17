from outreach.forms import MessageForm
from tests.base import OutreachMailTagTestCase


class HostVariableFormTests(OutreachMailTagTestCase):
    def form(self, **fields: str) -> MessageForm:
        return MessageForm({"subject": "Hello", "body": "<p>Hi</p>", **fields})

    def test_a_registered_variable_is_accepted_in_the_subject_and_the_body(self) -> None:
        self.register_variable(lambda prospect: "Pro", "plan_name")

        form = self.form(subject="Your {{ plan_name | plan }}", body="<p>{{ plan_name }}</p>")

        self.assertTrue(form.is_valid(), form.errors)

    def test_an_unregistered_variable_is_refused_with_the_full_list(self) -> None:
        self.register_variable(lambda prospect: "Pro", "plan_name")

        form = self.form(subject="{{ coupon }}")

        self.assertFalse(form.is_valid())
        message = form.errors["subject"][0]
        self.assertIn("coupon", message)
        self.assertIn("first_name", message)
        self.assertIn("plan_name", message)

    def test_without_the_registration_the_variable_is_unknown(self) -> None:
        form = self.form(subject="{{ plan_name }}")

        self.assertFalse(form.is_valid())

    def test_a_bare_word_tag_argument_can_name_a_registered_variable(self) -> None:
        self.register_variable(lambda prospect: "Pro", "plan_name")
        self.register_echo_tag()

        form = self.form(subject="{% echo plan_name %}")

        self.assertTrue(form.is_valid(), form.errors)
