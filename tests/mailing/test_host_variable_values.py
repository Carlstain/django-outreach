from outreach.models import Prospect
from outreach.services.variables import MailVariables
from tests.base import OutreachMailTagTestCase
from tests.factories import ProspectFactory


class HostVariableValuesTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.calls: list[str] = []
        self.prospect = ProspectFactory(first_name="Ada")

    def register_counting_variable(self, name: str, result: object) -> None:
        def variable(prospect: Prospect) -> object:
            self.calls.append(name)
            return result

        self.register_variable(variable, name)

    def test_a_variable_the_message_does_not_use_is_never_computed(self) -> None:
        self.register_counting_variable("plan_name", "Pro")

        MailVariables().render(
            "Hello {{ first_name }}", MailVariables().values_for(self.prospect), html=False
        )

        self.assertEqual(self.calls, [])

    def test_a_used_variable_is_computed_once_per_recipient_however_often_it_is_used(
        self,
    ) -> None:
        self.register_counting_variable("plan_name", "Pro")
        variables = MailVariables()
        values = variables.values_for(self.prospect)

        rendered = variables.render("{{ plan_name }} {{ plan_name }}", values, html=False)

        self.assertEqual(rendered, "Pro Pro")
        self.assertEqual(self.calls, ["plan_name"])
        variables.render("{{ plan_name }}", variables.values_for(self.prospect), html=False)
        self.assertEqual(self.calls, ["plan_name", "plan_name"])

    def test_checking_for_a_key_does_not_compute_it(self) -> None:
        self.register_counting_variable("plan_name", "Pro")

        values = MailVariables().values_for(self.prospect)

        self.assertIn("plan_name", values)
        self.assertNotIn("unknown_key", values)
        self.assertEqual(self.calls, [])

    def test_none_and_empty_text_take_the_fallback_and_other_values_become_text(self) -> None:
        self.register_counting_variable("nothing", None)
        self.register_counting_variable("empty", "")
        self.register_counting_variable("seats", 12)
        variables = MailVariables()

        rendered = variables.render(
            "{{ nothing | none yet }}, {{ empty | blank }}, {{ seats }}",
            variables.values_for(self.prospect),
            html=False,
        )

        self.assertEqual(rendered, "none yet, blank, 12")

    def test_the_preview_flag_reaches_a_variable_that_declares_it(self) -> None:
        seen: list[bool] = []

        def previewing(prospect: Prospect, *, preview: bool = False) -> str:
            seen.append(preview)
            return "placeholder" if preview else "real"

        self.register_variable(previewing, "coupon")
        variables = MailVariables()

        previewed = variables.render(
            "{{ coupon }}", variables.values_for(self.prospect, preview=True), html=False
        )
        sent = variables.render(
            "{{ coupon }}", variables.values_for(self.prospect), html=False
        )

        self.assertEqual((previewed, sent), ("placeholder", "real"))
        self.assertEqual(seen, [True, False])

    def test_extra_fixed_values_and_the_built_ins_are_available(self) -> None:
        values = MailVariables().values_for(
            self.prospect, extra={"unsubscribe_url": "https://x/"}
        )

        self.assertEqual(values["first_name"], "Ada")
        self.assertEqual(values["unsubscribe_url"], "https://x/")

    def test_registered_variables_are_allowed_and_listed_after_the_built_ins(self) -> None:
        self.register_counting_variable("plan_name", "Pro")
        variables = MailVariables()

        self.assertIn("plan_name", variables.allowed_keys())
        self.assertEqual(variables.catalog()[-1].key, "plan_name")
        self.assertEqual(variables.catalog()[0].key, "first_name")
