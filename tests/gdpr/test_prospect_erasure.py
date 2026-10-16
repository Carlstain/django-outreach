from django.contrib.auth import get_user_model

from outreach.choices import DeliveryStatus, EventKind, ProspectStatus
from outreach.models import Audience, Mailing, MailingDelivery, Prospect, ProspectEvent
from outreach.services.erasure import ProspectEraser
from outreach.services.unsubscribe import SuppressionList
from outreach.signals import prospect_erased
from tests.base import OutreachTestCase
from tests.factories import AudienceFactory, MailingFactory, ProspectFactory, UserFactory


class ProspectErasureTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailing = MailingFactory(sent_count=1, skipped_count=2)
        self.prospect = ProspectFactory()
        self.audience = AudienceFactory()
        self.prospect.audiences.add(self.audience)
        ProspectEvent.record(self.prospect, EventKind.ADDED, "staff")
        MailingDelivery.objects.create(
            mailing=self.mailing, prospect=self.prospect, status=DeliveryStatus.SENT
        )
        self.receiver = self.connect_receiver(prospect_erased)

    def erase(self, *prospects: Prospect) -> int:
        queryset = Prospect.objects.filter(pk__in=[prospect.pk for prospect in prospects])
        return ProspectEraser().erase(queryset, "staff")

    def test_the_prospect_and_what_belongs_to_it_are_deleted(self) -> None:
        other_prospect = ProspectFactory()
        ProspectEvent.record(other_prospect, EventKind.ADDED, "staff")

        self.erase(self.prospect)

        self.assertFalse(Prospect.objects.filter(pk=self.prospect.pk).exists())
        self.assertFalse(ProspectEvent.objects.filter(prospect_id=self.prospect.pk).exists())
        self.assertFalse(MailingDelivery.objects.filter(prospect_id=self.prospect.pk).exists())
        self.assertTrue(Audience.objects.filter(pk=self.audience.pk).exists())
        self.assertEqual(ProspectEvent.objects.filter(prospect=other_prospect).count(), 1)

    def test_mailings_keep_their_counts(self) -> None:
        self.erase(self.prospect)

        mailing = Mailing.objects.get(pk=self.mailing.pk)
        self.assertEqual((mailing.sent_count, mailing.skipped_count), (1, 2))

    def test_the_address_stays_suppressed_so_an_import_comes_back_unsubscribed(self) -> None:
        email = self.prospect.email

        self.erase(self.prospect)

        self.assertTrue(SuppressionList().contains(email))
        self.assertEqual(
            Prospect.objects.create(email=email).status, ProspectStatus.UNSUBSCRIBED
        )

    def test_a_linked_user_account_is_not_touched(self) -> None:
        user = UserFactory()
        self.prospect.user = user
        self.prospect.save()

        self.erase(self.prospect)

        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())

    def test_the_signal_is_sent_after_commit_with_the_address_and_the_actor(self) -> None:
        email = self.prospect.email

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.erase(self.prospect)

        self.receiver.assert_not_called()
        for callback in callbacks:
            callback()
        arguments = self.receiver.call_args.kwargs
        self.assertEqual(arguments["sender"], ProspectEraser)
        self.assertEqual((arguments["email"], arguments["actor"]), (email, "staff"))

    def test_many_prospects_are_erased_together_and_the_count_is_returned(self) -> None:
        second_prospect = ProspectFactory()
        kept_prospect = ProspectFactory()

        with self.captureOnCommitCallbacks(execute=True):
            count = self.erase(self.prospect, second_prospect)

        self.assertEqual(count, 2)
        self.assertEqual(list(Prospect.objects.all()), [kept_prospect])
        self.assertTrue(SuppressionList().contains(second_prospect.email))
        self.assertFalse(SuppressionList().contains(kept_prospect.email))
        self.assertEqual(self.receiver.call_count, 2)

    def test_erasing_a_prospect_that_is_already_gone_changes_nothing(self) -> None:
        stale_prospect = Prospect.objects.get(pk=self.prospect.pk)
        self.prospect.delete()

        with self.captureOnCommitCallbacks(execute=True):
            count = self.erase(stale_prospect)

        self.assertEqual(count, 0)
        self.receiver.assert_not_called()
