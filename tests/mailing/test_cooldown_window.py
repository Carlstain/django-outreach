from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.choices import SkipReason
from outreach.services.mailing import ProspectMailer
from tests.base import MAIL_BASE_URL, OutreachTestCase
from tests.factories import ProspectFactory


class CooldownWindowTests(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")

    def test_the_default_window_is_ten_seconds(self) -> None:
        just_mailed = ProspectFactory(last_mailed_at=timezone.now() - timedelta(seconds=3))
        mailed_earlier = ProspectFactory(last_mailed_at=timezone.now() - timedelta(seconds=11))

        mail_plan = self.mailer.plan([just_mailed, mailed_earlier])

        self.assertEqual(mail_plan.recipients, [mailed_earlier])
        self.assertEqual(
            [skipped.reason for skipped in mail_plan.skipped], [SkipReason.COOLDOWN]
        )

    @override_settings(OUTREACH_RESEND_COOLDOWN=timedelta(0))
    def test_a_zero_window_turns_the_cooldown_off(self) -> None:
        just_mailed = ProspectFactory(last_mailed_at=timezone.now())

        mail_plan = self.mailer.plan([just_mailed])

        self.assertEqual(mail_plan.recipients, [just_mailed])

    def test_the_cooldown_ends_one_window_after_the_last_mail(self) -> None:
        last_mailed_at = timezone.now()

        self.assertEqual(
            ProspectMailer.cooldown_ends_at(last_mailed_at),
            last_mailed_at + timedelta(seconds=10),
        )
        self.assertIsNone(ProspectMailer.cooldown_ends_at(None))
