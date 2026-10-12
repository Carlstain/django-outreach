from datetime import datetime

from django.test import override_settings

from tests.base import OutreachMailTagTestCase
from tests.factories import ProspectFactory, UserFactory


@override_settings(OUTREACH_LANGUAGE="en", TIME_ZONE="UTC")
class MailTagBuiltinsTests(OutreachMailTagTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.prospect = ProspectFactory()

    def test_today_uses_the_default_date_format(self) -> None:
        with self.freeze_time(hour=9):
            rendered = self.render_mail(self.prospect, subject="{% today %}")

        self.assertEqual(rendered.subject, "May 14, 2026")

    def test_today_accepts_a_date_format(self) -> None:
        with self.freeze_time(hour=9):
            rendered = self.render_mail(self.prospect, subject='{% today "j F Y" %}')

        self.assertEqual(rendered.subject, "14 May 2026")

    @override_settings(USE_TZ=False)
    def test_today_works_without_time_zone_support(self) -> None:
        rendered = self.render_mail(ProspectFactory(), subject='{% today "Y" %}')

        self.assertEqual(rendered.subject, str(datetime.now().year))

    def test_greeting_follows_the_hour_of_the_day(self) -> None:
        expected_by_hour = {
            0: "Good morning",
            11: "Good morning",
            12: "Good afternoon",
            17: "Good afternoon",
            18: "Good evening",
            23: "Good evening",
        }
        for hour, expected in expected_by_hour.items():
            with self.subTest(hour=hour), self.freeze_time(hour=hour):
                rendered = self.render_mail(self.prospect, subject="{% greeting %}")

                self.assertEqual(rendered.subject, expected)

    def test_member_since_is_empty_without_a_linked_user(self) -> None:
        rendered = self.render_mail(ProspectFactory(user=None), subject="[{% member_since %}]")

        self.assertEqual(rendered.subject, "[]")

    def test_member_since_uses_the_join_date_of_the_linked_user(self) -> None:
        user = UserFactory()
        prospect = ProspectFactory(user=user)

        rendered = self.render_mail(prospect, subject='{% member_since "Y-m-d" %}')

        self.assertEqual(rendered.subject, user.date_joined.strftime("%Y-%m-%d"))
