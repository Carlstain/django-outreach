from django.core.exceptions import ImproperlyConfigured

from outreach.models import Prospect
from outreach.services.mail_variables import MailVariableLibrary
from tests.base import OutreachMailTagTestCase


class MailVariableRegistryTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = MailVariableLibrary()

    def test_a_registered_variable_is_listed_under_its_function_name_sorted(self) -> None:
        @self.library.register(label="Plan", example="Pro")
        def plan_name(prospect: Prospect) -> str:
            return "Pro"

        @self.library.register(label="Coupon", example="SAVE10", name="coupon")
        def other_function(prospect: Prospect) -> str:
            return "SAVE10"

        catalog = self.library.catalog()
        self.assertEqual([variable.name for variable in catalog], ["coupon", "plan_name"])
        self.assertEqual(catalog[1].label, "Plan")
        self.assertEqual(catalog[1].example, "Pro")

    def test_a_duplicate_name_is_refused(self) -> None:
        @self.library.register(label="First", example="1", name="same")
        def first(prospect: Prospect) -> str:
            return "1"

        with self.assertRaisesMessage(ImproperlyConfigured, "already registered"):

            @self.library.register(label="Second", example="2", name="same")
            def second(prospect: Prospect) -> str:
                return "2"

    def test_a_name_that_is_not_a_word_is_refused(self) -> None:
        for name in ["two words", "dash-ed", " "]:
            with self.subTest(name=name), self.assertRaises(ImproperlyConfigured):

                @self.library.register(label="Bad", example="x", name=name)
                def bad(prospect: Prospect) -> str:
                    return "x"

    def test_the_built_in_variables_the_button_tag_and_registered_tags_are_reserved(
        self,
    ) -> None:
        self.register_tag(lambda prospect: "tag output", "taken_by_a_tag")

        for name in ["first_name", "unsubscribe_url", "button", "taken_by_a_tag"]:
            with (
                self.subTest(name=name),
                self.assertRaisesMessage(ImproperlyConfigured, "reserved"),
            ):

                @self.library.register(label="Bad", example="x", name=name)
                def bad(prospect: Prospect) -> str:
                    return "x"

    def test_a_tag_can_not_take_the_name_of_a_registered_variable(self) -> None:
        self.register_variable(lambda prospect: "Pro", "plan_name")

        with self.assertRaisesMessage(ImproperlyConfigured, "reserved"):
            self.register_tag(lambda prospect: "tag output", "plan_name")

    def test_the_signature_follows_the_rules_of_tags(self) -> None:
        with self.assertRaisesMessage(ImproperlyConfigured, "first parameter"):

            @self.library.register(label="No parameter", example="x")
            def no_parameter() -> str:
                return "x"

        with self.assertRaisesMessage(ImproperlyConfigured, "needs a default value"):

            @self.library.register(label="Needs more", example="x")
            def needs_more(prospect: Prospect, other: str) -> str:
                return other

        with self.assertRaisesMessage(ImproperlyConfigured, "keyword-only"):

            @self.library.register(label="Positional", example="x")
            def positional(prospect: Prospect, preview: bool = False) -> str:
                return "x"

    def test_a_keyword_only_preview_parameter_is_detected(self) -> None:
        @self.library.register(label="Previewing", example="x")
        def previewing(prospect: Prospect, *, preview: bool = False) -> str:
            return "x"

        @self.library.register(label="Plain", example="x")
        def plain(prospect: Prospect) -> str:
            return "x"

        accepts_preview = {v.name: v.accepts_preview for v in self.library.catalog()}
        self.assertEqual(accepts_preview, {"plain": False, "previewing": True})
