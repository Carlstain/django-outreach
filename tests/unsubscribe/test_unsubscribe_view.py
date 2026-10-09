from django.test import Client, override_settings

from outreach.choices import ACTOR_RECIPIENT, EventKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent, Suppression
from outreach.services.unsubscribe import SuppressionList, UnsubscribeTokens
from tests.base import OutreachTestCase
from tests.factories import ProspectFactory
from tests.routes import outreach_unsubscribe_url


@override_settings(OUTREACH_LANGUAGE="en")
class UnsubscribeViewTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.prospect = ProspectFactory()
        self.url = outreach_unsubscribe_url(UnsubscribeTokens().make(self.prospect))

    def test_get_shows_confirmation_without_unsubscribing(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.status, ProspectStatus.PROSPECT)
        self.assertFalse(SuppressionList().contains(self.prospect.email))
        self.assertNotIn(self.prospect.email, response.content.decode())

    def test_post_unsubscribes_and_suppresses_the_address(self) -> None:
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.status, ProspectStatus.UNSUBSCRIBED)
        self.assertTrue(SuppressionList().contains(self.prospect.email))
        event = ProspectEvent.objects.get(prospect=self.prospect, kind=EventKind.UNSUBSCRIBED)
        self.assertEqual(event.actor, ACTOR_RECIPIENT)

    def test_one_click_post_unsubscribes_without_csrf_token(self) -> None:
        response = self.client.post(
            self.url,
            data="List-Unsubscribe=One-Click",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(response.status_code, 200)
        self.prospect.refresh_from_db()
        self.assertEqual(self.prospect.status, ProspectStatus.UNSUBSCRIBED)

    def test_invalid_token_is_not_found(self) -> None:
        invalid_url = outreach_unsubscribe_url("not-a-valid-token")

        get_response = self.client.get(invalid_url)
        post_response = self.client.post(invalid_url)

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.assertEqual(Suppression.objects.count(), 0)

    def test_unsubscribing_twice_is_harmless(self) -> None:
        first_response = self.client.post(self.url)
        second_response = self.client.post(self.url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Suppression.objects.count(), 1)
        self.assertEqual(
            Prospect.objects.get(pk=self.prospect.pk).status, ProspectStatus.UNSUBSCRIBED
        )

    def test_deleted_prospect_get_shows_done_page_and_changes_nothing(self) -> None:
        self.prospect.delete()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outreach/unsubscribed.html")
        self.assertEqual(response.context["masked_email"], "")
        self.assertEqual(Suppression.objects.count(), 0)

    def test_deleted_prospect_post_shows_done_page(self) -> None:
        self.prospect.delete()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "outreach/unsubscribed.html")
        self.assertEqual(Prospect.objects.count(), 0)

    def test_forged_token_is_not_found_on_get_and_post(self) -> None:
        forged_url = outreach_unsubscribe_url(UnsubscribeTokens().make(self.prospect) + "x")

        self.assertEqual(self.client.get(forged_url).status_code, 404)
        self.assertEqual(self.client.post(forged_url).status_code, 404)

    def test_get_masks_the_local_part_with_bullets(self) -> None:
        prospect = ProspectFactory(email="claire@example.com")
        response = self.client.get(
            outreach_unsubscribe_url(UnsubscribeTokens().make(prospect))
        )

        self.assertEqual(response.context["masked_email"], "c•••••@example.com")
