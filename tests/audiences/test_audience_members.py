from outreach.choices import EventKind
from outreach.models import Prospect, ProspectEvent
from outreach.services.audiences import AudienceMembers
from tests.base import OutreachTestCase
from tests.factories import AudienceFactory, ProspectFactory


class AudienceMembersTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.audience = AudienceFactory(name="Spring fair")
        self.members = AudienceMembers()

    def test_adding_counts_only_the_new_members(self) -> None:
        already_in = ProspectFactory()
        newcomer = ProspectFactory()
        self.audience.prospects.add(already_in)

        added = self.members.add(
            self.audience,
            Prospect.objects.filter(pk__in=[already_in.pk, newcomer.pk]),
            "staff",
        )

        self.assertEqual(added, 1)
        self.assertEqual(set(self.audience.prospects.all()), {already_in, newcomer})

    def test_adding_records_one_event_per_new_member(self) -> None:
        already_in = ProspectFactory()
        newcomer = ProspectFactory()
        self.audience.prospects.add(already_in)

        self.members.add(
            self.audience,
            Prospect.objects.filter(pk__in=[already_in.pk, newcomer.pk]),
            "staff",
        )

        event = ProspectEvent.objects.get(kind=EventKind.AUDIENCE_ADDED)
        self.assertEqual(
            (event.prospect, event.detail, event.actor), (newcomer, "Spring fair", "staff")
        )

    def test_adding_twice_changes_nothing_the_second_time(self) -> None:
        prospects = Prospect.objects.filter(pk=ProspectFactory().pk)
        self.members.add(self.audience, prospects, "staff")

        added_again = self.members.add(self.audience, prospects, "staff")

        self.assertEqual(added_again, 0)
        self.assertEqual(
            ProspectEvent.objects.filter(kind=EventKind.AUDIENCE_ADDED).count(), 1
        )

    def test_removing_counts_only_the_former_members_and_records_events(self) -> None:
        member = ProspectFactory()
        outsider = ProspectFactory()
        self.audience.prospects.add(member)

        removed = self.members.remove(
            self.audience, Prospect.objects.filter(pk__in=[member.pk, outsider.pk]), "staff"
        )

        self.assertEqual(removed, 1)
        self.assertFalse(self.audience.prospects.exists())
        event = ProspectEvent.objects.get(kind=EventKind.AUDIENCE_REMOVED)
        self.assertEqual((event.prospect, event.detail), (member, "Spring fair"))

    def test_removing_twice_changes_nothing_the_second_time(self) -> None:
        member = ProspectFactory()
        self.audience.prospects.add(member)
        prospects = Prospect.objects.filter(pk=member.pk)
        self.members.remove(self.audience, prospects, "staff")

        removed_again = self.members.remove(self.audience, prospects, "staff")

        self.assertEqual(removed_again, 0)
        self.assertEqual(
            ProspectEvent.objects.filter(kind=EventKind.AUDIENCE_REMOVED).count(), 1
        )

    def test_the_event_actor_and_detail_are_cut_to_their_columns(self) -> None:
        long_audience = AudienceFactory(name="n" * 120)
        actor = "a" * 300

        self.members.add(
            long_audience, Prospect.objects.filter(pk=ProspectFactory().pk), actor
        )

        event = ProspectEvent.objects.get(kind=EventKind.AUDIENCE_ADDED)
        self.assertEqual(len(event.actor), 150)
