from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from outreach.models import Mailing
from outreach.tasks import deliver_mail
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import (
    outreach_mailing_cancel_schedule_url,
    outreach_mailing_change_url,
    outreach_mailing_changelist_url,
)


class ScheduledMailingAdminTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(
            create_outreach_staff_user(["view_prospect", "view_mailing", "change_prospect"])
        )
        self.prospect = ProspectFactory(first_name="Alice", last_name="Martin")
        self.mailing = self.scheduler.schedule(
            [self.prospect],
            "Subject",
            "<p>Body</p>",
            send_at=timezone.now() + timedelta(days=1),
        ).mailing

    def test_the_detail_shows_the_schedule_the_scheduled_recipients_and_a_cancel_button(
        self,
    ) -> None:
        response = self.client.get(outreach_mailing_change_url(self.mailing.pk))

        self.assertContains(response, "Scheduled for")
        self.assertContains(response, "Alice Martin")
        self.assertContains(response, "scheduled</span>")
        self.assertContains(response, outreach_mailing_cancel_schedule_url(self.mailing.pk))

    def test_the_list_shows_the_scheduled_time(self) -> None:
        response = self.client.get(outreach_mailing_changelist_url())

        self.assertContains(response, "Scheduled for")

    def test_cancelling_deletes_the_mailing_and_returns_to_the_list(self) -> None:
        response = self.client.post(
            outreach_mailing_cancel_schedule_url(self.mailing.pk), follow=True
        )

        self.assertRedirects(response, outreach_mailing_changelist_url())
        self.assertContains(response, "The scheduled mailing was cancelled.")
        self.assertFalse(Mailing.objects.exists())

    def test_a_mailing_that_has_started_can_not_be_cancelled(self) -> None:
        with (
            patch.object(deliver_mail, "apply_async"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.scheduler.start(self.mailing)

        response = self.client.post(
            outreach_mailing_cancel_schedule_url(self.mailing.pk), follow=True
        )

        self.assertContains(response, "already started")
        self.assertTrue(Mailing.objects.exists())

    def test_cancelling_needs_the_change_prospect_permission(self) -> None:
        self.client.force_login(create_outreach_staff_user(["view_prospect", "view_mailing"]))

        detail_response = self.client.get(outreach_mailing_change_url(self.mailing.pk))
        cancel_response = self.client.post(
            outreach_mailing_cancel_schedule_url(self.mailing.pk)
        )

        self.assertNotContains(
            detail_response, outreach_mailing_cancel_schedule_url(self.mailing.pk)
        )
        self.assertEqual(cancel_response.status_code, 403)
        self.assertTrue(Mailing.objects.exists())

    def test_cancelling_only_accepts_post(self) -> None:
        response = self.client.get(outreach_mailing_cancel_schedule_url(self.mailing.pk))

        self.assertEqual(response.status_code, 405)
