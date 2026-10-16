from smtplib import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPDataError,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)

from outreach.choices import FailureKind
from outreach.services.failures import FailureClassifier, MessageNotAccepted
from outreach.services.mail_buttons import InvalidButtonLink
from tests.base import OutreachTestCase


class FailureClassifierTests(OutreachTestCase):
    def test_a_refusal_by_the_server_is_refused(self) -> None:
        for error in [
            SMTPRecipientsRefused({}),
            SMTPSenderRefused(550, b"no", "sender@example.org"),
            SMTPDataError(554, b"rejected"),
            MessageNotAccepted("nothing delivered"),
        ]:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(FailureClassifier().classify(error), FailureKind.REFUSED)

    def test_a_connection_or_system_error_is_server(self) -> None:
        for error in [
            SMTPServerDisconnected("down"),
            SMTPConnectError(421, b"busy"),
            SMTPAuthenticationError(535, b"bad credentials"),
            ConnectionRefusedError(),
            TimeoutError(),
        ]:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(FailureClassifier().classify(error), FailureKind.SERVER)

    def test_anything_else_is_content(self) -> None:
        for error in [
            InvalidButtonLink("empty link"),
            RuntimeError("tag exploded"),
            ValueError(),
        ]:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(FailureClassifier().classify(error), FailureKind.CONTENT)
