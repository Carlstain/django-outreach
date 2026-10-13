from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, CommandParser

from outreach.services.user_loading import UserProspectLoader


class Command(BaseCommand):
    help = "Create a prospect for each user account that has none. Existing prospects are untouched."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run", action="store_true", help="Print the counts and write nothing."
        )
        parser.add_argument(
            "--include-inactive", action="store_true", help="Also load inactive users."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        loader = UserProspectLoader(
            dry_run=options["dry_run"], include_inactive=options["include_inactive"]
        )
        try:
            report = loader.load()
        except ImproperlyConfigured as error:
            raise CommandError(str(error)) from error
        prefix = "Dry run, nothing written. " if options["dry_run"] else ""
        self.stdout.write(
            f"{prefix}Users selected: {report.selected}. "
            f"Prospects created: {report.created} "
            f"(unsubscribed: {report.unsubscribed}). "
            f"Already prospects: {report.existing}. Invalid: {report.invalid}."
        )
