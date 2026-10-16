from collections.abc import Callable
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from django.dispatch import Signal
from django.test import TestCase, TransactionTestCase

from outreach.models import Prospect
from outreach.services.mail_tags import mail_tag_library
from outreach.services.mailing import ProspectMailer, RenderedMail

MAIL_BASE_URL = "https://outreach.example.test"


class OutreachTestCase(TestCase):
    def connect_receiver(self, signal: Signal) -> Mock:
        receiver = Mock()
        signal.connect(receiver, weak=False)
        self.addCleanup(signal.disconnect, receiver)
        return receiver


class OutreachTransactionTestCase(TransactionTestCase):
    pass


class OutreachMailTagTestCase(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        registry_patcher = patch.dict(mail_tag_library.tags)
        registry_patcher.start()
        self.addCleanup(registry_patcher.stop)
        self.echo_calls: list[tuple[str, ...]] = []

    def register_tag(
        self, function: Callable[..., str], name: str, example: str = "SAMPLE"
    ) -> None:
        mail_tag_library.register(label=name, example=example, name=name)(function)

    def register_echo_tag(self) -> None:
        def echo(prospect: Prospect, *arguments: str) -> str:
            self.echo_calls.append(arguments)
            return " ".join(arguments)

        self.register_tag(echo, "echo")

    def render_mail(
        self,
        prospect: Prospect,
        subject: str = "Subject",
        body: str = "<p>Body</p>",
        *,
        preview: bool = False,
    ) -> RenderedMail:
        return ProspectMailer(MAIL_BASE_URL, "staff").render(
            prospect, subject, body, preview=preview
        )

    def freeze_time(self, hour: int) -> object:
        return patch(
            "django.utils.timezone.now",
            return_value=datetime(2026, 5, 14, hour, 30, tzinfo=timezone.utc),
        )
