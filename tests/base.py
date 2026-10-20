from collections.abc import Callable
from datetime import datetime, timezone
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.conf import settings
from django.dispatch import Signal
from django.test import TestCase, TransactionTestCase, override_settings

from outreach.models import Prospect
from outreach.services.mail_tags import mail_tag_library
from outreach.services.mail_variables import mail_variable_library
from outreach.services.mailing import ProspectMailer, RenderedMail
from outreach.services.scheduling import MailingScheduler
from outreach.tasks import deliver_mail, release_deliveries

MAIL_BASE_URL = "https://outreach.example.test"

requires_translations = skipUnless(
    settings.USE_I18N, "Nothing is translated when USE_I18N is False."
)


class OutreachTestCase(TestCase):
    def connect_receiver(self, signal: Signal) -> Mock:
        receiver = Mock()
        signal.connect(receiver, weak=False)
        self.addCleanup(signal.disconnect, receiver)
        return receiver


class OutreachTransactionTestCase(TransactionTestCase):
    pass


@override_settings(
    OUTREACH_BASE_URL=MAIL_BASE_URL, OUTREACH_LANGUAGE="en", OUTREACH_DISPATCH="celery"
)
class CeleryMailTestCase(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.mailer = ProspectMailer(MAIL_BASE_URL, "staff")
        self.scheduler = MailingScheduler(self.mailer)
        publisher = patch.object(deliver_mail, "apply_async")
        self.apply_async = publisher.start()
        self.addCleanup(publisher.stop)
        release_publisher = patch.object(release_deliveries, "apply_async")
        self.release_apply_async = release_publisher.start()
        self.addCleanup(release_publisher.stop)


class OutreachMailTagTestCase(OutreachTestCase):
    def setUp(self) -> None:
        super().setUp()
        for registry in (mail_tag_library.tags, mail_variable_library.variables):
            registry_patcher = patch.dict(registry)
            registry_patcher.start()
            self.addCleanup(registry_patcher.stop)
        self.echo_calls: list[tuple[str, ...]] = []

    def register_tag(
        self, function: Callable[..., str], name: str, example: str = "SAMPLE"
    ) -> None:
        mail_tag_library.register(label=name, example=example, name=name)(function)

    def register_variable(
        self, function: Callable[..., object], name: str, example: str = "SAMPLE"
    ) -> None:
        mail_variable_library.register(label=name, example=example, name=name)(function)

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
