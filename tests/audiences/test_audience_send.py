from django.core import mail
from django.test import override_settings

from outreach.choices import ProspectStatus
from outreach.models import Mailing
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import AudienceFactory, ProspectFactory, create_outreach_staff_user
from tests.routes import outreach_prospect_changelist_url


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class AudienceSendTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(create_outreach_staff_user())
        self.audience = AudienceFactory()
        self.first_member = ProspectFactory()
        self.second_member = ProspectFactory()
        self.unsubscribed_member = ProspectFactory(status=ProspectStatus.UNSUBSCRIBED)
        self.outsider = ProspectFactory()
        self.audience.prospects.add(
            self.first_member, self.second_member, self.unsubscribed_member
        )
        self.filtered_url = f"{outreach_prospect_changelist_url()}?audience={self.audience.pk}"

    def test_the_compose_page_lists_the_members_who_can_be_mailed(self) -> None:
        response = self.client.post(
            self.filtered_url,
            {
                "action": "send_mail",
                "index": "0",
                "_selected_action": [str(self.first_member.pk)],
                "select_across": "1",
            },
        )

        plan = response.context["plan"]
        self.assertEqual(set(plan.recipients), {self.first_member, self.second_member})
        self.assertEqual(
            [(skipped.prospect, skipped.reason.value) for skipped in plan.skipped],
            [(self.unsubscribed_member, "unsubscribed")],
        )

    def test_sending_with_select_across_reaches_only_the_members_who_can_be_mailed(
        self,
    ) -> None:
        self.client.post(
            self.filtered_url,
            {
                "action": "send_mail",
                "index": "0",
                "_selected_action": [str(self.first_member.pk)],
                "select_across": "1",
                "is_newsletter": "on",
                "step": "send",
                "subject": "Thanks for coming",
                "body": "Hello,\n\nSee you next year.",
            },
        )

        self.assertEqual(
            {message.to[0] for message in mail.outbox},
            {self.first_member.email, self.second_member.email},
        )
        mailing = Mailing.objects.get()
        self.assertEqual((mailing.sent_count, mailing.skipped_count), (2, 1))
