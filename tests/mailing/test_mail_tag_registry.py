from django.core.exceptions import ImproperlyConfigured

from outreach.models import Prospect
from outreach.services.mail_tags import MailTagLibrary, mail_tag_library
from tests.base import OutreachTestCase


class MailTagRegistryTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.library = MailTagLibrary()

    def test_a_registered_tag_is_listed_under_its_function_name(self) -> None:
        @self.library.register(label="Shout", example="HEY")
        def shout(prospect: Prospect, text: str = "") -> str:
            return text.upper()

        self.assertEqual([tag.name for tag in self.library.catalog()], ["shout"])

    def test_an_explicit_name_replaces_the_function_name(self) -> None:
        @self.library.register(label="Shout", example="HEY", name="loud")
        def shout(prospect: Prospect) -> str:
            return "HEY"

        self.assertEqual([tag.name for tag in self.library.catalog()], ["loud"])

    def test_a_duplicate_name_is_refused(self) -> None:
        @self.library.register(label="First", example="1", name="same")
        def first(prospect: Prospect) -> str:
            return "1"

        with self.assertRaises(ImproperlyConfigured):

            @self.library.register(label="Second", example="2", name="same")
            def second(prospect: Prospect) -> str:
                return "2"

    def test_a_parameter_after_the_prospect_without_a_default_is_refused(self) -> None:
        with self.assertRaises(ImproperlyConfigured):

            @self.library.register(label="Strict", example="x")
            def strict(prospect: Prospect, required: str) -> str:
                return required

    def test_a_function_without_the_prospect_parameter_is_refused(self) -> None:
        with self.assertRaises(ImproperlyConfigured):

            @self.library.register(label="Empty", example="x")
            def empty() -> str:
                return ""

    def test_variadic_and_defaulted_parameters_are_accepted(self) -> None:
        @self.library.register(label="Flexible", example="x")
        def flexible(prospect: Prospect, first: str = "", *rest: str, **options: str) -> str:
            return first

        self.assertEqual([tag.name for tag in self.library.catalog()], ["flexible"])

    def test_a_keyword_only_preview_parameter_is_detected(self) -> None:
        @self.library.register(label="Aware", example="x")
        def aware(prospect: Prospect, *, preview: bool = False) -> str:
            return ""

        @self.library.register(label="Plain", example="x")
        def plain(prospect: Prospect) -> str:
            return ""

        self.assertTrue(self.library.tags["aware"].accepts_preview)
        self.assertFalse(self.library.tags["plain"].accepts_preview)

    def test_a_positional_preview_parameter_is_refused(self) -> None:
        with self.assertRaises(ImproperlyConfigured):

            @self.library.register(label="Open", example="x")
            def open_to_staff(prospect: Prospect, preview: bool = False) -> str:
                return ""

    def test_the_button_name_is_reserved(self) -> None:
        with self.assertRaises(ImproperlyConfigured):

            @self.library.register(label="Button", example="x")
            def button(prospect: Prospect) -> str:
                return ""

    def test_a_name_equal_to_a_variable_key_is_refused(self) -> None:
        for variable_key in ("first_name", "unsubscribe_url"):
            with self.subTest(name=variable_key), self.assertRaises(ImproperlyConfigured):
                self.library.register(label="Clash", example="x", name=variable_key)(
                    lambda prospect: ""
                )

    def test_the_shared_library_lists_the_built_in_tags(self) -> None:
        names = {tag.name for tag in mail_tag_library.catalog()}

        self.assertLessEqual({"today", "greeting", "member_since"}, names)
