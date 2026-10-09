from collections.abc import Iterable

from django.core import signing
from django.utils.crypto import salted_hmac

from outreach.choices import EventKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent, Suppression

SUPPRESSION_SALT = "outreach.suppression"
UNSUBSCRIBE_SALT = "outreach.unsubscribe"


class SuppressionList:
    def hash(self, email: str) -> str:
        return salted_hmac(SUPPRESSION_SALT, email.strip().lower()).hexdigest()

    def contains(self, email: str) -> bool:
        return Suppression.objects.filter(email_hash=self.hash(email)).exists()

    def add(self, email: str) -> None:
        Suppression.objects.get_or_create(email_hash=self.hash(email))

    def filter_suppressed(self, emails: Iterable[str]) -> set[str]:
        email_by_hash = {self.hash(email): email for email in emails}
        suppressed_hashes = Suppression.objects.filter(
            email_hash__in=email_by_hash.keys()
        ).values_list("email_hash", flat=True)
        return {email_by_hash[email_hash] for email_hash in suppressed_hashes}


class UnsubscribeTokens:
    def make(self, prospect: Prospect) -> str:
        return signing.dumps(str(prospect.pk), salt=UNSUBSCRIBE_SALT)

    def resolve(self, token: str) -> Prospect:
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
        SuppressionList().add(prospect.email)
        if prospect.status == ProspectStatus.UNSUBSCRIBED:
            return
        prospect.status = ProspectStatus.UNSUBSCRIBED
        prospect.save(update_fields=["status", "updated_at"])
        ProspectEvent.record(prospect, EventKind.UNSUBSCRIBED, actor)
