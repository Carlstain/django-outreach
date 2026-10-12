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

    def test_the_shared_library_lists_the_built_in_tags(self) -> None:
        names = {tag.name for tag in mail_tag_library.catalog()}

        self.assertLessEqual({"today", "greeting", "member_since"}, names)
