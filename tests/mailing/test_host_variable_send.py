from django.core import mail
from django.test import override_settings

from outreach.choices import EventKind, FailureKind
from outreach.models import Prospect, ProspectEvent
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachMailTagTestCase
from tests.factories import ProspectFactory, UserFactory


@override_settings(OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en")
class HostVariableSendTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")

    def test_a_raising_variable_fails_only_that_recipient_as_a_content_failure(self) -> None:
        def plan_name(prospect: Prospect) -> str:
            if prospect.first_name == "Broken":
                raise RuntimeError("plan lookup exploded")
            return "Pro"

        self.register_variable(plan_name, "plan_name")
        good = ProspectFactory(first_name="Ada")
        broken = ProspectFactory(first_name="Broken")

        report = self.mailer.send([good, broken], "Your {{ plan_name }} plan", "<p>Hi</p>")

        self.assertEqual(report.sent, [good])
        self.assertEqual(report.failed, [broken])
        self.assertEqual([message.subject for message in mail.outbox], ["Your Pro plan"])
        failure = ProspectEvent.objects.get(prospect=broken, kind=EventKind.MAIL_FAILED)
        self.assertEqual(failure.detail, FailureKind.CONTENT)

    def test_a_real_send_passes_false_and_a_test_send_passes_true(self) -> None:
        seen: list[bool] = []

        def coupon(prospect: Prospect, *, preview: bool = False) -> str:
            seen.append(preview)
            return "PLACEHOLDER" if preview else "REAL10"

        self.register_variable(coupon, "coupon")
        prospect = ProspectFactory()

        self.mailer.send([prospect], "{{ coupon }}", "<p>Hi</p>")
        self.mailer.send_sample(prospect, "{{ coupon }}", "<p>Hi</p>", "staff@example.org")

        self.assertEqual(seen, [False, True])
        self.assertEqual(
            [message.subject for message in mail.outbox], ["REAL10", "[Test] PLACEHOLDER"]
        )

    def test_a_variable_can_read_the_linked_user_of_the_delivered_prospect(self) -> None:
        def account_name(prospect: Prospect) -> str:
            return prospect.user.get_username() if prospect.user else ""

        self.register_variable(account_name, "account_name")
        user = UserFactory(username="ada_account")
        linked_prospect = ProspectFactory(user=user)
        unlinked_prospect = ProspectFactory()
        queued_mailing = self.mailer.queue(
            [linked_prospect, unlinked_prospect],
            "{{ account_name | none }}",
            "<p>Hi</p>",
            "",
            True,
        )

        for delivery in queued_mailing.deliveries:
            self.mailer.deliver(delivery.pk)

        self.assertEqual(
            sorted(message.subject for message in mail.outbox), ["ada_account", "none"]
        )
