from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from tests.base import CeleryMailTestCase
from tests.factories import (
    MailingDeliveryFactory,
    MailingFactory,
    ProspectFactory,
    create_outreach_staff_user,
)
from tests.routes import outreach_prospect_changelist_url


@override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=10)
class SendGatePreviewTests(CeleryMailTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())
        released_mailing = MailingFactory()
        for _ in range(4):
            MailingDeliveryFactory(
                mailing=released_mailing, released_at=timezone.now() - timedelta(minutes=10)
            )
        self.prospects = [ProspectFactory() for _ in range(15)]

    def preview(self, prospects: list | None = None, **extra_fields: str):
        selected = prospects if prospects is not None else self.prospects
        return self.client.post(
            outreach_prospect_changelist_url(),
            {
                "action": "send_mail",
                "_selected_action": [str(prospect.pk) for prospect in selected],
                "is_newsletter": "on",
                "step": "preview",
                "subject": "Welcome",
                "body": "Hello,\n\nJoin us.",
                **extra_fields,
            },
        )

    def test_preview_names_how_many_go_now_and_how_many_wait(self) -> None:
        response = self.preview()

        self.assertContains(response, "6 will be sent now")
        self.assertContains(response, "9 will wait")
        self.assertContains(response, "about 1\u00a0hour")
        self.assertContains(response, 'max="10" value="4"')

    def test_preview_shows_no_notice_when_everything_goes_now(self) -> None:
        response = self.preview(self.prospects[:3])

        self.assertNotContains(response, "will wait")

    def test_no_notice_for_a_scheduled_send(self) -> None:
        send_at = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")

        response = self.preview(send_at=send_at)

        self.assertNotContains(response, "will wait")

    @override_settings(OUTREACH_SEND_LIMIT_PER_HOUR=None)
    def test_no_notice_without_the_gate(self) -> None:
        response = self.preview()

        self.assertNotContains(response, "will wait")
        self.assertNotContains(response, "gauge-meter")
