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
    changes: dict[str, tuple[str, str]] = field(default_factory=dict)

    @property
    def cells(self) -> list[str]:
        return [self.values[name] for name in ProspectCsvColumns.NAMES]


@dataclass
class ImportPreview:
    rows: list[ImportRow] = field(default_factory=list)

    @property
    def invalid_rows(self) -> list[ImportRow]:
        return [row for row in self.rows if row.errors]

    def rows_with(self, status: ImportRowStatus) -> list[ImportRow]:
        return [row for row in self.rows if row.status == status]

    @property
    def new_rows(self) -> list[ImportRow]:
        return self.rows_with(ImportRowStatus.NEW)

    @property
    def update_rows(self) -> list[ImportRow]:
        return self.rows_with(ImportRowStatus.UPDATE)

    @property
    def kept_rows(self) -> list[ImportRow]:
        return self.rows_with(ImportRowStatus.SKIPPED)

    @property
    def repeated_rows(self) -> list[ImportRow]:
        return self.rows_with(ImportRowStatus.REPEATED)

    @property
    def skipped_count(self) -> int:
        return len(self.kept_rows) + len(self.repeated_rows)


@dataclass
class ImportResult:
    created: int
    updated: int


class ProspectCsvImporter:
    """Reads a CSV file of prospects and creates the ones that do not exist yet.

    Headers are stripped, lower-cased and mapped through ``OUTREACH_IMPORT_HEADER_ALIASES``.
    A row that repeats an earlier row of the file is never imported. A row whose email exists
    is skipped, unless the import updates existing prospects: then each filled cell that
    differs from the stored value replaces it, and an empty cell, or a column the file does not
    have, changes nothing. The email, status, account link, last mailed date and audiences of
    an existing prospect are never changed.
    """

    EMAIL_LOOKUP_CHUNK = 500

    def preview(self, text: str, update_existing: bool = False) -> ImportPreview:
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
        row_values = [self.row_values(record) for record in records]
        existing_by_email = self.existing_prospects([values["email"] for values in row_values])
        seen_emails: set[str] = set()
        for index, (record, values) in enumerate(
            zip(records, row_values, strict=True), start=2
        ):
            row = ImportRow(line=index, values=values)
            email = values["email"]
            if email in seen_emails:
                row.status = ImportRowStatus.REPEATED
            elif email in existing_by_email:
                self.compare_with_existing(
                    row, record, existing_by_email[email], update_existing
                )
            else:
                row.errors = self.validation_errors(values)
            seen_emails.add(email)
            preview.rows.append(row)
        return preview

    def apply(self, preview: ImportPreview, file_name: str) -> ImportResult:
        """Create the new rows and update the changed ones of a preview that has no error."""
        result = ImportResult(created=0, updated=0)
        with transaction.atomic():
            for row in preview.new_rows:
                if Prospect.objects.filter(email=row.values["email"]).exists():
                    continue
                prospect = Prospect(**row.values)
                prospect.save()
                ProspectEvent.record(
                    prospect, EventKind.IMPORTED, ACTOR_IMPORT, detail=file_name
                )
                result.created += 1
            for row in preview.update_rows:
                prospect = (
                    Prospect.objects.select_for_update()
                    .filter(email=row.values["email"])
                    .first()
                )
                if prospect is None:
                    continue
                changed = {
                    field_name: new_value
                    for field_name, (_old_value, new_value) in row.changes.items()
                    if getattr(prospect, field_name) != new_value
                }
                if not changed:
                    continue
                for field_name, new_value in changed.items():
                    setattr(prospect, field_name, new_value)
                prospect.save(update_fields=[*changed, "updated_at"])
                ProspectEvent.record(
                    prospect, EventKind.EDITED, ACTOR_IMPORT, detail=", ".join(changed)
                )
                result.updated += 1
        return result

    def existing_prospects(self, emails: list[str]) -> dict[str, dict[str, str]]:
        existing_by_email: dict[str, dict[str, str]] = {}
        unique_emails = sorted(set(emails))
        for start in range(0, len(unique_emails), self.EMAIL_LOOKUP_CHUNK):
            chunk = unique_emails[start : start + self.EMAIL_LOOKUP_CHUNK]
            for stored in Prospect.objects.filter(email__in=chunk).values(
                *ProspectCsvColumns.NAMES
            ):
                existing_by_email[stored["email"]] = stored
        return existing_by_email

    def compare_with_existing(
        self,
        row: ImportRow,
        record: dict[str, str | None],
        stored: dict[str, str],
        update_existing: bool,
    ) -> None:
        row.status = ImportRowStatus.SKIPPED
        if not update_existing:
            return
        for field_name in ProspectCsvColumns.NAMES:
            file_value = self.cell_value(record, field_name)
            if field_name != "email" and file_value and file_value != stored[field_name]:
                row.changes[field_name] = (stored[field_name], file_value)
        if row.changes:
            row.status = ImportRowStatus.UPDATE
            merged = {**stored, **{name: change[1] for name, change in row.changes.items()}}
            row.errors = self.validation_errors(merged)

    def cell_value(self, record: dict[str, str | None], name: str) -> str:
        value = (record.get(name) or "").strip()
        return value.lower() if name in ("email", "kind") else value

    def row_values(self, record: dict[str, str | None]) -> dict[str, str]:
        values = {name: self.cell_value(record, name) for name in ProspectCsvColumns.NAMES}
        values["kind"] = values["kind"] or ProspectKind.INDIVIDUAL
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
