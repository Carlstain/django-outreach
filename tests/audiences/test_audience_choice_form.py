from outreach.forms import AudienceChoiceForm
from tests.base import OutreachTestCase
from tests.factories import AudienceFactory


class AudienceChoiceFormTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.audience = AudienceFactory(name="Spring fair")

    def creating_form(self, **fields: str) -> AudienceChoiceForm:
        return AudienceChoiceForm(fields, creating=True)

    def test_an_existing_audience_alone_is_valid(self) -> None:
        form = self.creating_form(audience=str(self.audience.pk))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["audience"], self.audience)

    def test_a_new_name_alone_is_valid(self) -> None:
        form = self.creating_form(new_audience_name="Autumn fair")

        self.assertTrue(form.is_valid(), form.errors)

    def test_neither_is_refused(self) -> None:
        form = self.creating_form()

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.non_field_errors(), ["Choose an audience, or type the name of a new one."]
        )

    def test_both_are_refused(self) -> None:
        form = self.creating_form(audience=str(self.audience.pk), new_audience_name="Autumn")

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.non_field_errors(), ["Choose an audience or type a new name, not both."]
        )

    def test_a_blank_name_counts_as_no_name(self) -> None:
        form = self.creating_form(new_audience_name="   ")

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.non_field_errors(), ["Choose an audience, or type the name of a new one."]
        )

    def test_a_name_that_exists_ignoring_case_is_refused_without_a_second_error(self) -> None:
        form = self.creating_form(new_audience_name="SPRING fair")

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["new_audience_name"], ["An audience with this name already exists."]
        )
        self.assertEqual(form.non_field_errors(), [])

    def test_a_name_longer_than_the_column_is_refused(self) -> None:
        form = self.creating_form(new_audience_name="n" * 121)

        self.assertFalse(form.is_valid())
        self.assertIn("new_audience_name", form.errors)

    def test_the_form_for_removing_has_no_name_field_and_needs_an_audience(self) -> None:
        form = AudienceChoiceForm({"new_audience_name": "Autumn fair"})

        self.assertNotIn("new_audience_name", form.fields)
        self.assertFalse(form.is_valid())
        self.assertIn("audience", form.errors)
