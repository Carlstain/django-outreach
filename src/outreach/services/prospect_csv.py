import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import capfirst
from django.utils.translation import gettext as _

from outreach.choices import ACTOR_IMPORT, EventKind, ImportRowStatus, ProspectKind
from outreach.conf import outreach_settings
from outreach.models import Prospect, ProspectEvent

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class CsvImportError(Exception):
    """The file cannot be read as a prospect list, whatever its rows contain."""


class ProspectCsvColumns:
    NAMES = ["email", "first_name", "last_name", "organization", "city", "country", "kind"]

    def labels(self) -> list[str]:
        return [
            str(capfirst(Prospect._meta.get_field(name).verbose_name)) for name in self.NAMES
        ]

    def with_aliases(self) -> list[dict[str, object]]:
        header_aliases = outreach_settings.import_header_aliases
        return [
            {
                "name": name,
                "aliases": [
                    alias for alias, target in header_aliases.items() if target == name
                ],
            }
            for name in self.NAMES
        ]


@dataclass
class ImportRow:
    line: int
    values: dict[str, str]
    status: ImportRowStatus = ImportRowStatus.NEW
    errors: list[str] = field(default_factory=list)

    @property
    def cells(self) -> list[str]:
        return [self.values[name] for name in ProspectCsvColumns.NAMES]


@dataclass
class ImportPreview:
    rows: list[ImportRow] = field(default_factory=list)

    @property
    def invalid_rows(self) -> list[ImportRow]:
        return [row for row in self.rows if row.errors]

    @property
    def new_rows(self) -> list[ImportRow]:
        return [row for row in self.rows if row.status == ImportRowStatus.NEW]

    @property
    def skipped_count(self) -> int:
        return len(self.rows) - len(self.new_rows)


class ProspectCsvImporter:
    """Reads a CSV file of prospects and creates the ones that do not exist yet.

    Headers are stripped, lower-cased and mapped through ``OUTREACH_IMPORT_HEADER_ALIASES``.
    A row whose email exists, or repeats an earlier row, is skipped and never updated.
    """

    def preview(self, text: str) -> ImportPreview:
        """Validate every row without saving anything.

        Raises:
            CsvImportError: The file is empty, has no email column or has too many rows.
        """
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise CsvImportError(_("The file is empty."))
        header_aliases = outreach_settings.import_header_aliases
        normalised_headers = [header.strip().lower() for header in reader.fieldnames]
        reader.fieldnames = [
            header_aliases.get(header, header) for header in normalised_headers
        ]
        if "email" not in reader.fieldnames:
            raise CsvImportError(_("The file has no email column."))
        records = list(reader)
        maximum = outreach_settings.max_import_rows
        if len(records) > maximum:
            raise CsvImportError(
                _("The file has %(count)d rows, the limit is %(limit)d.")
                % {"count": len(records), "limit": maximum}
            )
        preview = ImportPreview()
        seen_emails: set[str] = set()
        for index, record in enumerate(records, start=2):
            values = self.row_values(record)
            row = ImportRow(line=index, values=values)
            email = values["email"]
            if email in seen_emails or Prospect.objects.filter(email=email).exists():
                row.status = ImportRowStatus.SKIPPED
            else:
                row.errors = self.validation_errors(values)
                seen_emails.add(email)
            preview.rows.append(row)
        return preview

    def apply(self, preview: ImportPreview, file_name: str) -> int:
        """Create the new rows of a preview that has no error, and return how many."""
        created_count = 0
        with transaction.atomic():
            for row in preview.new_rows:
                if Prospect.objects.filter(email=row.values["email"]).exists():
                    continue
                prospect = Prospect(**row.values)
                prospect.save()
                ProspectEvent.record(
                    prospect, EventKind.IMPORTED, ACTOR_IMPORT, detail=file_name
                )
                created_count += 1
        return created_count

    def row_values(self, record: dict[str, str | None]) -> dict[str, str]:
        values = {name: (record.get(name) or "").strip() for name in ProspectCsvColumns.NAMES}
        values["email"] = values["email"].lower()
        values["kind"] = values["kind"].lower() or ProspectKind.INDIVIDUAL
        return values

    def validation_errors(self, values: dict[str, str]) -> list[str]:
        try:
            Prospect(**values).full_clean(validate_unique=False)
        except ValidationError as error:
            return [
                f"{self.field_label(field_name)}: {message}"
                for field_name, messages in error.message_dict.items()
                for message in messages
            ]
        return []

    def field_label(self, field_name: str) -> str:
        if field_name not in ProspectCsvColumns.NAMES:
            return field_name
        return str(capfirst(Prospect._meta.get_field(field_name).verbose_name))


class ProspectCsvExporter:
    """Writes prospects as CSV with the same columns the importer reads.

    Cells that a spreadsheet would read as a formula get a leading apostrophe.
    """

    def to_csv(self, prospects: Iterable[Prospect]) -> str:
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(ProspectCsvColumns().labels())
        for prospect in prospects:
            writer.writerow(
                [self.safe_cell(getattr(prospect, name)) for name in ProspectCsvColumns.NAMES]
            )
        return stream.getvalue()

    def safe_cell(self, value: object) -> str:
        text = str(value)
        return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text
