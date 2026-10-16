from dataclasses import dataclass

from django.db import IntegrityError, transaction

from outreach.choices import ACTOR_SYSTEM, EventKind, ProspectKind, ProspectStatus
from outreach.models import Prospect, ProspectEvent
from outreach.signals import prospect_subscribed, send_after_commit


@dataclass
class SubscribeResult:
    prospect: Prospect
    created: bool


class ProspectSubscriptions:
    """Creates prospects for a signup form of the host project."""

    def subscribe(
        self,
        email: str,
        *,
        consent_source: str,
        first_name: str = "",
        last_name: str = "",
        organization: str = "",
        city: str = "",
        country: str = "",
        kind: ProspectKind = ProspectKind.INDIVIDUAL,
        actor: str = ACTOR_SYSTEM,
    ) -> SubscribeResult:
        """Create a prospect from a consent the host project collected.

        The host owns the consent, the double opt-in included. An existing prospect is returned
        unchanged, and an unsubscribed one stays unsubscribed. A new prospect goes through
        ``Prospect.save``, so a suppressed address is created as unsubscribed and a matching
        user is linked. A *subscribed* event records ``consent_source``, and the
        ``prospect_subscribed`` signal is sent after commit unless the new prospect is
        unsubscribed.

        Raises:
            ValueError: ``consent_source`` is empty.
            django.core.exceptions.ValidationError: The data does not validate.
        """
        consent_source = consent_source.strip()
        if not consent_source:
            raise ValueError("consent_source is required")
        normalised_email = email.strip().lower()
        existing_prospect = Prospect.objects.filter(email=normalised_email).first()
        if existing_prospect is not None:
            return SubscribeResult(existing_prospect, created=False)
        prospect = Prospect(
            email=normalised_email,
            kind=kind,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            city=city,
            country=country,
        )
        prospect.full_clean(validate_unique=False)
        try:
            with transaction.atomic():
                prospect.save()
                ProspectEvent.record(
                    prospect, EventKind.SUBSCRIBED, actor, detail=consent_source
                )
        except IntegrityError:
            return SubscribeResult(Prospect.objects.get(email=normalised_email), created=False)
        if prospect.status != ProspectStatus.UNSUBSCRIBED:
            send_after_commit(
                prospect_subscribed,
                ProspectSubscriptions,
                prospect=prospect,
                consent_source=consent_source,
            )
        return SubscribeResult(prospect, created=True)
