from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from outreach.forms import MessageForm
from tests.base import OutreachTestCase


class MessageFormSendAtTests(OutreachTestCase):
    def form(self, **fields: str) -> MessageForm:
        return MessageForm({"subject": "Subject", "body": "Hello", **fields})

    @override_settings(OUTREACH_DISPATCH="celery")
    def test_the_field_exists_in_celery_mode_and_is_optional(self) -> None:
        form = self.form()

        self.assertIn("send_at", form.fields)
        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data["send_at"])

    @override_settings(OUTREACH_DISPATCH="sync")
    def test_the_field_is_absent_in_sync_mode(self) -> None:
        form = self.form(send_at="2999-01-01T10:00")

        self.assertNotIn("send_at", form.fields)
        self.assertTrue(form.is_valid())

    @override_settings(OUTREACH_DISPATCH="celery")
    def test_a_time_in_the_future_is_accepted(self) -> None:
        future = timezone.template_localtime(timezone.now() + timedelta(days=1))

        form = self.form(send_at=future.strftime("%Y-%m-%dT%H:%M"))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNotNone(form.cleaned_data["send_at"])

    @override_settings(OUTREACH_DISPATCH="celery")
    def test_a_time_in_the_past_is_refused(self) -> None:
        form = self.form(send_at="2000-01-01T10:00")

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["send_at"], ["Choose a time in the future."])
