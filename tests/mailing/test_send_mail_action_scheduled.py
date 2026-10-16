from datetime import timedelta
from unittest.mock import patch

from django.contrib.messages import SUCCESS, get_messages
from django.test import override_settings
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.models import Mailing
from outreach.tasks import deliver_mail
from tests.base import CeleryMailTestCase
from tests.factories import ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url


class SendMailActionScheduledTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())
        self.prospects = [ProspectFactory(), ProspectFactory()]
        self.send_at = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")

    def post_step(self, step: str, **extra_fields: str):
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [str(prospect.pk) for prospect in self.prospects],
                "is_newsletter": "on",
                "step": step,
                "subject": "Welcome",
                "body": "Hello,\n\nJoin us.",
                **extra_fields,
            },
        )

    def test_the_compose_page_offers_a_send_time(self) -> None:
        response = self.post_step("compose")

        self.assertContains(response, 'name="send_at"')

    def test_the_preview_offers_to_schedule_and_carries_the_time(self) -> None:
        response = self.post_step("preview", send_at=self.send_at)

        self.assertContains(response, "Schedule for 2 prospects")
        self.assertContains(response, f'name="send_at" value="{self.send_at}"')

    def test_a_time_in_the_past_sends_the_user_back_to_the_compose_page(self) -> None:
        response = self.post_step("preview", send_at="2000-01-01T10:00")

        self.assertContains(response, "Choose a time in the future.")
        self.assertContains(response, "Step 1 of 2")

    def test_the_send_step_schedules_the_mailing_and_queues_nothing(self) -> None:
        with (
            patch.object(deliver_mail, "apply_async") as apply_async,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.post_step("send", send_at=self.send_at)

        self.assertEqual(response.status_code, 302)
        messages = list(get_messages(response.wsgi_request))
        self.assertRegex(messages[0].message, r"^2 scheduled for .+, 0 skipped\.$")
        self.assertEqual(messages[0].level, SUCCESS)
        apply_async.assert_not_called()
        mailing = Mailing.objects.get()
        self.assertIsNotNone(mailing.scheduled_for)
        self.assertEqual(
            set(mailing.deliveries.values_list("status", flat=True)),
            {DeliveryStatus.SCHEDULED},
        )

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_the_compose_page_has_no_send_time_in_sync_mode(self) -> None:
        response = self.post_step("compose")

        self.assertNotContains(response, 'name="send_at"')
