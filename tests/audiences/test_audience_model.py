from django.db import IntegrityError, transaction

from outreach.forms import AudienceForm
from outreach.models import Audience, Prospect
from tests.base import OutreachTestCase
from tests.factories import AudienceFactory, ProspectFactory


class AudienceModelTests(OutreachTestCase):
    def test_name_must_be_unique_ignoring_case(self) -> None:
        AudienceFactory(name="Spring fair")

        form = AudienceForm({"name": "sPRING FAIR", "description": ""})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["name"], ["An audience with this name already exists."])

    def test_database_refuses_names_that_differ_only_by_case(self) -> None:
        AudienceFactory(name="Spring fair")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Audience.objects.create(name="SPRING FAIR")

        self.assertEqual(Audience.objects.count(), 1)

    def test_editing_an_audience_keeps_its_own_name_valid(self) -> None:
        audience = AudienceFactory(name="Spring fair")

        form = AudienceForm({"name": "Spring fair", "description": "New"}, instance=audience)

        self.assertTrue(form.is_valid(), form.errors)

    def test_deleting_an_audience_keeps_its_prospects(self) -> None:
        audience = AudienceFactory()
        prospect = ProspectFactory()
        audience.prospects.add(prospect)

        audience.delete()

        self.assertTrue(Prospect.objects.filter(pk=prospect.pk).exists())

    def test_deleting_a_prospect_removes_its_memberships_only(self) -> None:
        audience = AudienceFactory()
        leaving = ProspectFactory()
        staying = ProspectFactory()
        audience.prospects.add(leaving, staying)

        leaving.delete()

        self.assertEqual(list(audience.prospects.all()), [staying])
