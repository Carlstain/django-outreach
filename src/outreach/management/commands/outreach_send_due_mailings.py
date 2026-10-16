from typing import Any

from django.core.management.base import BaseCommand, CommandError

from outreach.services.scheduling import MailingScheduler, SchedulingUnavailable


class Command(BaseCommand):
    help = "Start the scheduled mailings whose time has come. Run it every minute or so."

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            handled_count = MailingScheduler.start_due()
        except SchedulingUnavailable as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Mailings started: {handled_count}.")
