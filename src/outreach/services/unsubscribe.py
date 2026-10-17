from collections.abc import Iterable

from django.conf import settings
from django.core import signing
from django.utils.crypto import salted_hmac

from outreach.choices import EventKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent, Suppression
from outreach.signals import prospect_unsubscribed, send_after_commit

SUPPRESSION_SALT = "outreach.suppression"
UNSUBSCRIBE_SALT = "outreach.unsubscribe"


class SuppressionList:
    """Permanent do-not-mail list, stored as salted HMAC hashes of the addresses."""

    def hashes(self, email: str) -> list[str]:
        normalised_email = email.strip().lower()
        secret_keys = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
        return [
            salted_hmac(SUPPRESSION_SALT, normalised_email, secret=secret_key).hexdigest()
            for secret_key in secret_keys
        ]

    def hash(self, email: str) -> str:
        return self.hashes(email)[0]

    def contains(self, email: str) -> bool:
        return Suppression.objects.filter(email_hash__in=self.hashes(email)).exists()

    def add(self, email: str) -> None:
        Suppression.objects.get_or_create(email_hash=self.hash(email))

    def add_many(self, emails: Iterable[str]) -> None:
        Suppression.objects.bulk_create(
            [Suppression(email_hash=self.hash(email)) for email in emails],
            ignore_conflicts=True,
        )

    def filter_suppressed(self, emails: Iterable[str]) -> set[str]:
        email_by_hash = {
            email_hash: email for email in emails for email_hash in self.hashes(email)
        }
        suppressed_hashes = Suppression.objects.filter(
            email_hash__in=email_by_hash.keys()
        ).values_list("email_hash", flat=True)
        return {email_by_hash[email_hash] for email_hash in suppressed_hashes}


class UnsubscribeTokens:
    """Signed, non-expiring tokens carried by unsubscribe links."""

    def make(self, prospect: Prospect) -> str:
        return signing.dumps(str(prospect.pk), salt=UNSUBSCRIBE_SALT)

    def resolve(self, token: str) -> Prospect:
        """Return the prospect of a token.

        Raises:
            Prospect.DoesNotExist: The signature is bad or the prospect no longer exists.
        """
        try:
            prospect_pk = signing.loads(token, salt=UNSUBSCRIBE_SALT)
        except signing.BadSignature as error:
            raise Prospect.DoesNotExist from error
        return Prospect.objects.get(pk=prospect_pk)

    def is_signed(self, token: str) -> bool:
        try:
            signing.loads(token, salt=UNSUBSCRIBE_SALT)
        except signing.BadSignature:
            return False
        return True


class ProspectUnsubscriber:
    def unsubscribe(self, prospect: Prospect, actor: str) -> None:
        """Suppress the address, mark the prospect unsubscribed and record the event.

        Calling it again on an unsubscribed prospect records nothing more. The
        ``prospect_unsubscribed`` signal is sent after commit, once per real change.
        """
        SuppressionList().add(prospect.email)
        if prospect.status == ProspectStatus.UNSUBSCRIBED:
            return
        prospect.status = ProspectStatus.UNSUBSCRIBED
        prospect.save(update_fields=["status", "updated_at"])
        ProspectEvent.record(prospect, EventKind.UNSUBSCRIBED, actor)
        send_after_commit(
            prospect_unsubscribed, ProspectUnsubscriber, prospect=prospect, actor=actor
        )
