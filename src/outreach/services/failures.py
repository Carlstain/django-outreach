import smtplib

from outreach.choices import FailureKind


class MessageNotAccepted(Exception):
    """The mail server took the message but delivered nothing."""


class FailureClassifier:
    """Names why a delivery failed, without keeping anything the error says."""

    REFUSED_ERRORS = (
        smtplib.SMTPRecipientsRefused,
        smtplib.SMTPSenderRefused,
        smtplib.SMTPDataError,
        MessageNotAccepted,
    )

    def classify(self, error: Exception) -> FailureKind:
        """Return the kind of a delivery error.

        A refusal by the server is ``refused``, any other operating system or connection error
        is ``server``, and everything else, such as a bad button link or a computed tag that
        raises, is ``content``.
        """
        if isinstance(error, self.REFUSED_ERRORS):
            return FailureKind.REFUSED
        if isinstance(error, OSError):
            return FailureKind.SERVER
        return FailureKind.CONTENT

    def smtp_codes(self, error: Exception) -> str:
        """Return the numeric SMTP reply codes of an error, never the text that came with them."""
        if isinstance(error, smtplib.SMTPRecipientsRefused):
            codes = {code for code, _ in error.recipients.values()}
        elif isinstance(error, smtplib.SMTPResponseException):
            codes = {error.smtp_code}
        else:
            codes = set()
        return ",".join(str(code) for code in sorted(codes))
