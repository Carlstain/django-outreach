from typing import Any

import tablib
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from import_export import resources

from outreach.choices import ACTOR_IMPORT, EventKind, ProspectKind
from outreach.conf import outreach_settings
from outreach.models import Prospect, ProspectEvent

IMPORT_FIELD_NAMES = [
    "email",
    "first_name",
    "last_name",
    "organization",
    "city",
    "country",
    "kind",
]


def import_columns() -> list[dict[str, Any]]:
    header_aliases = outreach_settings.import_header_aliases
    return [
        {
            "name": field_name,
            "aliases": [
                alias for alias, target in header_aliases.items() if target == field_name
            ],
        }
        for field_name in IMPORT_FIELD_NAMES
    ]


class ProspectResource(resources.ModelResource):
    class Meta:
        model = Prospect
        import_id_fields = ["email"]
        clean_model_instances = True
        fields = IMPORT_FIELD_NAMES

    def get_export_headers(self, selected_fields: list[str] | None = None) -> list[str]:
        return [
            str(capfirst(Prospect._meta.get_field(field.attribute).verbose_name))
            for field in self.get_export_fields(selected_fields)
            if field
        ]

    def before_import(self, dataset: tablib.Dataset, **kwargs: Any) -> None:
        if dataset.headers:
            header_aliases = outreach_settings.import_header_aliases
            normalised_headers = [str(header).strip().lower() for header in dataset.headers]
            dataset.headers = [
                header_aliases.get(header, header) for header in normalised_headers
            ]
        if len(dataset) > outreach_settings.max_import_rows:
            # INFO - M.E. - 07/10/26 - the import keeps iterating after a before_import
            # error, so the rows are dropped to stop an oversized file being processed
            row_count = len(dataset)
            dataset.wipe()
            raise ValueError(
                _("The file has %(count)d rows, the limit is %(limit)d.")
                % {"count": row_count, "limit": outreach_settings.max_import_rows}
            )

    def before_import_row(self, row: dict[str, Any], **kwargs: Any) -> None:
        row["email"] = str(row.get("email") or "").strip().lower()
        row["kind"] = str(row.get("kind") or "").strip().lower() or ProspectKind.INDIVIDUAL

    def skip_row(
        self,
        instance: Prospect,
        original: Prospect | None,
        row: dict[str, Any],
        import_validation_errors: dict[str, Any] | None = None,
    ) -> bool:
        return not instance._state.adding

    def after_save_instance(
        self, instance: Prospect, row: dict[str, Any], **kwargs: Any
    ) -> None:
        ProspectEvent.record(
            instance,
            EventKind.IMPORTED,
            ACTOR_IMPORT,
            detail=str(kwargs.get("file_name") or ""),
        )
