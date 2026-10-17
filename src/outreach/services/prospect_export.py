from datetime import datetime
from typing import Any

from outreach.models import Prospect


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class ProspectDataExporter:
    """Gathers everything stored about a prospect, to answer a request for access."""

    def export(self, prospect: Prospect) -> dict[str, Any]:
        """Return the data of a prospect as plain values that ``json.dumps`` accepts.

        It holds the profile, the linked account name, the audiences, the history and the
        deliveries. Mailings are named by their subject.
        """
        return {
            "email": prospect.email,
            "kind": prospect.kind,
            "first_name": prospect.first_name,
            "last_name": prospect.last_name,
            "organization": prospect.organization,
            "city": prospect.city,
            "country": prospect.country,
            "status": prospect.status,
            "account": prospect.user.get_username() if prospect.user else None,
            "last_mailed_at": isoformat_or_none(prospect.last_mailed_at),
            "created_at": isoformat_or_none(prospect.created_at),
            "updated_at": isoformat_or_none(prospect.updated_at),
            "audiences": [audience.name for audience in prospect.audiences.order_by("name")],
            "events": [
                {
                    "kind": event.kind,
                    "detail": event.detail,
                    "actor": event.actor,
                    "created_at": isoformat_or_none(event.created_at),
                    "mailing": event.mailing.subject if event.mailing else None,
                }
                for event in prospect.events.select_related("mailing")
                .only("kind", "detail", "actor", "created_at", "mailing__subject")
                .order_by("created_at")
            ],
            "deliveries": [
                {
                    "mailing": delivery.mailing.subject,
                    "status": delivery.status,
                    "attempts": delivery.attempts,
                    "failure": delivery.failure_kind,
                    "created_at": isoformat_or_none(delivery.created_at),
                }
                for delivery in prospect.deliveries.select_related("mailing")
                .only("status", "attempts", "failure_kind", "created_at", "mailing__subject")
                .order_by("created_at")
            ],
        }
