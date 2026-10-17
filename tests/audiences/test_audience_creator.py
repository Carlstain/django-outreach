from outreach.models import Audience
from outreach.services.audiences import AudienceCreator, AudienceNameTaken
from tests.base import OutreachTestCase
from tests.factories import AudienceFactory, UserFactory


class AudienceCreatorTests(OutreachTestCase):
    def test_it_creates_the_audience_for_its_creator(self) -> None:
        creator = UserFactory()

        audience = AudienceCreator().create("Autumn fair", creator)

        audience.refresh_from_db()
        self.assertEqual(
            (audience.name, audience.created_by, audience.updated_by),
            ("Autumn fair", creator, creator),
        )

    def test_it_creates_an_audience_without_a_creator(self) -> None:
        audience = AudienceCreator().create("Autumn fair", None)

        self.assertIsNone(audience.created_by)

    def test_a_name_taken_ignoring_case_raises_and_creates_nothing(self) -> None:
        AudienceFactory(name="Spring fair")

        with self.assertRaises(AudienceNameTaken):
            AudienceCreator().create("SPRING FAIR", UserFactory())

        self.assertEqual(Audience.objects.count(), 1)
