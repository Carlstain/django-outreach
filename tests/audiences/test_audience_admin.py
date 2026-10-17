from unittest.mock import patch

from django.contrib.auth.base_user import AbstractBaseUser
from django.forms.models import BaseModelForm
from django.urls import reverse

from outreach.models import Audience, Prospect
from tests.base import OutreachTestCase
from tests.factories import (
    OUTREACH_AUDIENCE_PERMISSIONS,
    AudienceFactory,
    ProspectFactory,
    UserFactory,
    create_outreach_staff_user,
)
from tests.html_inspector import inspect_page
from tests.routes import (
    outreach_audience_add_url,
    outreach_audience_change_url,
    outreach_audience_changelist_url,
    outreach_audience_delete_url,
)

FORM_FIELDS = {"name": "Spring fair", "description": "Visitors of the fair"}


def staff_with(*audience_codenames: str) -> AbstractBaseUser:
    return create_outreach_staff_user(["view_prospect", *audience_codenames])


class AudienceAdminTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.staff_user = staff_with(*OUTREACH_AUDIENCE_PERMISSIONS)
        self.client.force_login(self.staff_user)

    def test_changelist_lists_audiences_by_name_with_their_member_counts(self) -> None:
        second = AudienceFactory(name="Second")
        first = AudienceFactory(name="First")
        first.prospects.add(ProspectFactory(), ProspectFactory())

        response = self.client.get(outreach_audience_changelist_url())

        result_list = list(response.context["cl"].result_list)
        self.assertEqual(result_list, [first, second])
        self.assertEqual([audience.members for audience in result_list], [2, 0])

    def test_search_looks_in_name_and_description(self) -> None:
        by_name = AudienceFactory(name="Autumn fair")
        by_description = AudienceFactory(name="Other", description="Autumn visitors")
        AudienceFactory(name="Spring fair")

        response = self.client.get(outreach_audience_changelist_url(), {"q": "autumn"})

        self.assertEqual(set(response.context["cl"].result_list), {by_name, by_description})

    def test_add_creates_an_audience_authored_by_the_user(self) -> None:
        response = self.client.post(outreach_audience_add_url(), FORM_FIELDS)

        self.assertEqual(response.status_code, 302)
        audience = Audience.objects.get()
        self.assertEqual(
            (audience.name, audience.description), ("Spring fair", "Visitors of the fair")
        )
        self.assertEqual(audience.created_by, self.staff_user)
        self.assertEqual(audience.updated_by, self.staff_user)

    def test_change_records_who_changed_it_and_keeps_the_creator(self) -> None:
        creator = UserFactory()
        audience = AudienceFactory(name="Original", created_by=creator)

        response = self.client.post(
            outreach_audience_change_url(audience.pk), {**FORM_FIELDS, "name": "Renamed"}
        )

        self.assertEqual(response.status_code, 302)
        audience.refresh_from_db()
        self.assertEqual(audience.name, "Renamed")
        self.assertEqual(audience.created_by, creator)
        self.assertEqual(audience.updated_by, self.staff_user)

    def test_delete_removes_the_audience_and_keeps_its_prospects(self) -> None:
        audience = AudienceFactory()
        prospect = ProspectFactory()
        audience.prospects.add(prospect)

        response = self.client.post(outreach_audience_delete_url(audience.pk), {"post": "yes"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Audience.objects.exists())
        self.assertTrue(Prospect.objects.filter(pk=prospect.pk).exists())

    def test_a_name_that_exists_is_a_form_error(self) -> None:
        AudienceFactory(name="Spring fair")

        response = self.client.post(
            outreach_audience_add_url(), {**FORM_FIELDS, "name": "spring FAIR"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["adminform"].form.errors["name"],
            ["An audience with this name already exists."],
        )
        self.assertEqual(Audience.objects.count(), 1)

    def test_a_name_clash_that_slips_past_validation_is_a_form_error_not_a_server_error(
        self,
    ) -> None:
        AudienceFactory(name="Spring fair")
        original_validate_unique = BaseModelForm.validate_unique
        skipped = []

        def skip_the_first_check(form: BaseModelForm) -> None:
            if not skipped:
                skipped.append(form)
                return
            original_validate_unique(form)

        with patch.object(BaseModelForm, "validate_unique", skip_the_first_check):
            response = self.client.post(outreach_audience_add_url(), FORM_FIELDS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Audience.objects.count(), 1)

    def test_view_permission_is_required_to_list_and_open(self) -> None:
        audience = AudienceFactory()
        self.client.force_login(staff_with())

        list_response = self.client.get(outreach_audience_changelist_url())
        detail_response = self.client.get(outreach_audience_change_url(audience.pk))

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(detail_response.status_code, 403)

    def test_view_only_staff_can_read_but_not_write(self) -> None:
        audience = AudienceFactory(name="Original", description="Stored description")
        self.client.force_login(staff_with("view_audience"))

        detail_response = self.client.get(outreach_audience_change_url(audience.pk))
        write_response = self.client.post(
            outreach_audience_change_url(audience.pk), {**FORM_FIELDS, "name": "Hijacked"}
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Stored description")
        self.assertEqual(write_response.status_code, 403)
        audience.refresh_from_db()
        self.assertEqual(audience.name, "Original")

    def test_add_permission_is_required_to_add(self) -> None:
        self.client.force_login(staff_with("view_audience", "change_audience"))

        response = self.client.post(outreach_audience_add_url(), FORM_FIELDS)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Audience.objects.exists())

    def test_delete_permission_is_required_to_delete(self) -> None:
        audience = AudienceFactory()
        self.client.force_login(staff_with("view_audience", "add_audience", "change_audience"))

        response = self.client.post(outreach_audience_delete_url(audience.pk), {"post": "yes"})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Audience.objects.filter(pk=audience.pk).exists())

    def test_nav_entry_is_shown_only_with_the_view_permission(self) -> None:
        audiences_url = outreach_audience_changelist_url()

        with_permission = inspect_page(
            self.client.get(reverse("outreach_admin:index")).content
        )
        self.client.force_login(staff_with())
        without_permission = inspect_page(
            self.client.get(reverse("outreach_admin:index")).content
        )

        self.assertTrue(with_permission.find("a", href=audiences_url))
        self.assertEqual(without_permission.find("a", href=audiences_url), [])

    def test_sidebar_count_reflects_the_number_of_audiences(self) -> None:
        AudienceFactory.create_batch(3)

        response = self.client.get(outreach_audience_changelist_url())

        self.assertEqual(response.context["counts"]["audiences"], 3)
