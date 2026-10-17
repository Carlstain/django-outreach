from django.db import transaction
from django.db.models import QuerySet

from outreach.models import Prospect
from outreach.services.unsubscribe import SuppressionList
from outreach.signals import prospect_erased, send_after_commit


class ProspectEraser:
    """Answers a request for erasure."""

    def erase(self, prospects: QuerySet[Prospect], actor: str) -> int:
        """Delete prospects and keep only the suppression hash of their addresses.

        The history, the deliveries and the audience memberships of the prospects go with them,
        while mailings keep their counts. A linked user account is not touched. The addresses
        stay in the suppression list, so they are never mailed again, even if they are imported
        again. Everything happens in one transaction. The ``prospect_erased`` signal is sent
        once per prospect after commit with its address, so that a host can erase its own
        copies.

        Returns:
            The number of prospects erased.
        """
        with transaction.atomic():
            email_by_pk = dict(prospects.values_list("pk", "email"))
            SuppressionList().add_many(email_by_pk.values())
            Prospect.objects.filter(pk__in=list(email_by_pk)).delete()
        for email in email_by_pk.values():
            send_after_commit(prospect_erased, ProspectEraser, email=email, actor=actor)
        return len(email_by_pk)
