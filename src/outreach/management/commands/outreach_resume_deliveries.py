from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.models import MailingDelivery
from outreach.services.mailing import ProspectMailer


class Command(BaseCommand):
    help = "Queue again the deliveries left pending, for example after a worker was killed."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--older-than",
            type=int,
            default=30,
            help="Only deliveries pending for more than this many minutes (default 30).",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Print the count and queue nothing."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        threshold = timezone.now() - timedelta(minutes=options["older_than"])
        stale_pks = list(
            MailingDelivery.objects.filter(
                status=DeliveryStatus.PENDING, updated_at__lt=threshold
            ).values_list("pk", flat=True)
        )
        if options["dry_run"]:
            self.stdout.write(f"Dry run, nothing queued. Stale deliveries: {len(stale_pks)}.")
            return
        ProspectMailer.enqueue(stale_pks)
        self.stdout.write(f"Deliveries queued: {len(stale_pks)}.")
