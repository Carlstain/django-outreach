import re

from django.core import mail
from django.test import override_settings

from outreach.forms import MessageForm
from outreach.services.mailing import ProspectMailer
from outreach.services.variables import MailVariables
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory, UserFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url, outreach_unsubscribe_prefix


@override_settings(OUTREACH_BASE_URL="https://outreach.example.test", OUTREACH_LANGUAGE="en")
class MailVariablesTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())

    def send_to(self, prospects: list, subject: str, body: str) -> object:
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [str(prospect.pk) for prospect in prospects],
                "step": "send",
                "subject": subject,
                "body": body,
            },
        )

    def test_variables_are_replaced_in_subject_html_and_text(self) -> None:
        prospect = ProspectFactory(
            first_name="Alex", last_name="Morgan", organization="Acme Inc."
        )

        self.send_to(
            [prospect],
            "Hello {{ first_name }}",
            "<p>{{ full_name }} of {{ organization }} ({{ email }})</p>",
        )

        message = mail.outbox[0]
        html_body = message.alternatives[0][0]
        self.assertEqual(message.subject, "Hello Alex")
        for part in (message.body, html_body):
            self.assertIn("Alex Morgan of Acme Inc.", part)
            self.assertIn(prospect.email, part)

    def test_city_and_country_are_available(self) -> None:
        prospect = ProspectFactory(city="Springfield", country="Freedonia")

        self.send_to([prospect], "News", "<p>{{ city }}, {{ country }}</p>")

        self.assertIn("Springfield, Freedonia", mail.outbox[0].body)

    def test_fallback_is_used_when_the_value_is_empty(self) -> None:
        prospect = ProspectFactory(first_name="")

        self.send_to(
            [prospect], "Hi {{ first_name | there }}", "<p>Dear {{ first_name|Friend }}</p>"
        )

        message = mail.outbox[0]
        self.assertEqual(message.subject, "Hi there")
        self.assertIn("Dear Friend", message.alternatives[0][0])

    def test_fallback_is_ignored_when_the_value_exists(self) -> None:
        prospect = ProspectFactory(first_name="Ada")

        self.send_to([prospect], "Hi {{ first_name | there }}", "<p>Body</p>")

        self.assertEqual(mail.outbox[0].subject, "Hi Ada")

    def test_empty_value_without_fallback_renders_nothing(self) -> None:
        prospect = ProspectFactory(first_name="")

        self.send_to([prospect], "Hello{{ first_name }}!", "<p>Body</p>")

        self.assertEqual(mail.outbox[0].subject, "Hello!")

    def test_fallback_with_an_ampersand_is_not_double_escaped(self) -> None:
        prospect = ProspectFactory(first_name="")

        self.send_to([prospect], "Hi", "<p>Dear {{ first_name | Madame & Monsieur }}</p>")

        html_body = mail.outbox[0].alternatives[0][0]
        self.assertIn("Madame &amp; Monsieur", html_body)
        self.assertNotIn("&amp;amp;", html_body)

    def test_unknown_variable_in_the_body_is_rejected_by_the_form(self) -> None:
        prospect = ProspectFactory()

        response = self.send_to([prospect], "Hello", "<p>Dear {{ firstname }}</p>")

        self.assertEqual(response.status_code, 200)
        self.assertIn("firstname", " ".join(response.context["form"].errors["body"]))
        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_variable_in_the_subject_is_rejected_by_the_form(self) -> None:
        prospect = ProspectFactory()

        response = self.send_to([prospect], "Hello {{ nickname }}", "<p>Body</p>")

        self.assertEqual(response.status_code, 200)
        self.assertIn("nickname", " ".join(response.context["form"].errors["subject"]))
        self.assertEqual(len(mail.outbox), 0)

    def test_unsubscribe_url_is_an_allowed_variable(self) -> None:
        prospect = ProspectFactory()

        response = self.send_to(
            [prospect], "Hello", '<p><a href="{{ unsubscribe_url }}">Leave</a></p>'
        )

        self.assertEqual(response.status_code, 302)
        message = mail.outbox[0]
        text_link = re.search(r"Leave \((https://[^)\s]+)\)", message.body)
        self.assertIsNotNone(text_link)
        unsubscribe_url = text_link.group(1)
        self.assertTrue(
            unsubscribe_url.startswith(
                f"https://outreach.example.test{outreach_unsubscribe_prefix()}"
            )
        )
        self.assertRegex(
            message.alternatives[0][0],
            rf'href="{re.escape(unsubscribe_url)}"[^>]*>Leave</a>',
        )
        self.assertEqual(message.extra_headers["List-Unsubscribe"], f"<{unsubscribe_url}>")

    def test_script_in_a_first_name_is_escaped_in_the_html_part(self) -> None:
        prospect = ProspectFactory(first_name="<script>alert(1)</script>")

        self.send_to([prospect], "Hello", "<p>Dear {{ first_name }}</p>")

        html_body = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("<script>alert(1)</script>", html_body)
        self.assertIn("&lt;script&gt;", html_body)

    def test_line_breaks_in_a_value_cannot_inject_subject_headers(self) -> None:
        prospect = ProspectFactory(first_name="Ada\r\nBcc: attacker@test.com")

        self.send_to([prospect], "Hello {{ first_name }}", "<p>Body</p>")

        subject = mail.outbox[0].subject
        self.assertNotIn("\n", subject)
        self.assertNotIn("\r", subject)
        self.assertEqual(mail.outbox[0].bcc, [])

    def test_names_fall_back_to_the_linked_user(self) -> None:
        user = UserFactory(first_name="Grace", last_name="Hopper")
        prospect = ProspectFactory(first_name="", last_name="", user=user)

        self.send_to([prospect], "Hi {{ first_name }}", "<p>{{ full_name }}</p>")

        self.assertEqual(mail.outbox[0].subject, "Hi Grace")
        self.assertIn("Grace Hopper", mail.outbox[0].body)

    def test_prospect_names_win_over_the_linked_user(self) -> None:
        user = UserFactory(first_name="Grace", last_name="Hopper")
        prospect = ProspectFactory(first_name="Ada", last_name="Lovelace", user=user)

        self.send_to([prospect], "Hi {{ first_name }}", "<p>{{ full_name }}</p>")

        self.assertEqual(mail.outbox[0].subject, "Hi Ada")
        self.assertIn("Ada Lovelace", mail.outbox[0].body)

    def test_spacing_and_pipe_variants_are_all_recognised(self) -> None:
        values = {"first_name": "Ada", "city": ""}
        variables = MailVariables()

        rendered = variables.render(
            "{{first_name}}|{{  first_name  }}|{{ city | Paris }}|{{ city|Paris }}|{{city |Paris}}",
            values,
            html=False,
        )

        self.assertEqual(rendered, "Ada|Ada|Paris|Paris|Paris")

    def test_unknown_keys_are_reported_and_known_ones_are_not(self) -> None:
        variables = MailVariables()

        unknown = variables.unknown_keys(
            "{{ first_name }} {{ unsubscribe_url }} {{ nope | x }} {{ other }}"
        )

        self.assertEqual(unknown, {"nope", "other"})

    def test_catalog_lists_every_key_in_order(self) -> None:
        keys = [variable.key for variable in MailVariables().catalog()]

        self.assertEqual(keys, list(MailVariables.KEYS))

    def test_malformed_placeholders_are_rejected_in_body_and_subject(self) -> None:
        malformed_texts = [
            "{{ first_name | a|b }}",
            "{{ first_name | {{ city }} }}",
            "{{ <strong>first_name</strong> }}",
            "{{ first_name",
            "first_name }}",
        ]
        for malformed_text in malformed_texts:
            with self.subTest(malformed_text=malformed_text):
                body_form = MessageForm(
                    {"subject": "Hello", "body": f"<p>{malformed_text}</p>"}
                )
                subject_form = MessageForm({"subject": malformed_text, "body": "<p>Body</p>"})

                self.assertIn("Malformed variable", " ".join(body_form.errors["body"]))
                self.assertIn("Malformed variable", " ".join(subject_form.errors["subject"]))

    def test_every_valid_placeholder_form_is_accepted(self) -> None:
        valid_texts = [
            "{{first_name}}",
            "{{ first_name }}",
            "{{   first_name   }}",
            "{{ first_name | friend }}",
            "{{first_name|friend}}",
            "{{ unsubscribe_url }}",
        ]
        for valid_text in valid_texts:
            with self.subTest(valid_text=valid_text):
                form = MessageForm({"subject": valid_text, "body": f"<p>{valid_text}</p>"})

                self.assertTrue(form.is_valid(), form.errors)

    def test_hostile_value_cannot_become_a_javascript_link(self) -> None:
        prospect = ProspectFactory(organization="javascript:alert(1)")
        mailer = ProspectMailer("https://outreach.example.test", "tester")

        rendered = mailer.render(prospect, "Hi", '<p><a href="{{ organization }}">Go</a></p>')

        self.assertNotIn("javascript:", rendered.html)

    def test_unsubscribe_link_survives_the_second_sanitising_pass(self) -> None:
        prospect = ProspectFactory()
        mailer = ProspectMailer("https://outreach.example.test", "tester")

        rendered = mailer.render(
            prospect, "Hi", '<p><a href="{{ unsubscribe_url }}">Leave</a></p>'
        )

        self.assertIn(
            f'href="https://outreach.example.test{outreach_unsubscribe_prefix()}',
            rendered.html,
        )

    def test_markup_in_a_value_is_still_escaped(self) -> None:
        prospect = ProspectFactory(first_name="<img src=x onerror=alert(1)>")
        mailer = ProspectMailer("https://outreach.example.test", "tester")

        rendered = mailer.render(prospect, "Hi", "<p>Dear {{ first_name }}</p>")

        self.assertNotIn("<img", rendered.html)
        self.assertIn("&lt;img", rendered.html)
