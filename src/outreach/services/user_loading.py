import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction

from outreach.choices import ACTOR_SYSTEM, EventKind, ProspectStatus, SyncUsersMode
from outreach.conf import outreach_settings
from outreach.models import Prospect, ProspectEvent
from outreach.services.linking import UserLinker
from outreach.services.unsubscribe import SuppressionList

logger = logging.getLogger("outreach")

HOOK_FIELD_NAMES = {"kind", "first_name", "last_name", "organization", "city", "country"}


@dataclass
class UserLoadReport:
    """Counts from a load: users selected, prospects created, and why others were not."""

    selected: int = 0
    created: int = 0
    existing: int = 0
    unsubscribed: int = 0
    invalid: int = 0


class UserProspectLoader:
    """Turns host users into prospects, as the ``outreach_load_users`` command does.

    Args:
        dry_run: Count what would happen without saving anything.
        include_inactive: Also load users whose ``is_active`` is false.
    """

    def __init__(self, dry_run: bool = False, include_inactive: bool = False) -> None:
        self.dry_run = dry_run
        self.include_inactive = include_inactive

    def load(self) -> UserLoadReport:
        """Create a prospect for each user that has no prospect yet, in one transaction.

        Goes through ``Prospect.save()``, so linking and suppression apply: a suppressed
        address becomes an unsubscribed prospect. Users whose data fails validation are
        counted as invalid.
        """
        user_model = get_user_model()
        email_field_name = user_model.get_email_field_name()
        users = user_model.objects.exclude(**{f"{email_field_name}__isnull": True}).exclude(
            **{email_field_name: ""}
        )
        has_is_active = any(field.name == "is_active" for field in user_model._meta.fields)
        if has_is_active and not self.include_inactive:
            users = users.filter(is_active=True)

        known_emails = set(Prospect.objects.values_list("email", flat=True))
        linked_user_pks = set(
            Prospect.objects.exclude(user=None).values_list("user_id", flat=True)
        )
        suppression_list = SuppressionList()
        report = UserLoadReport()
        with transaction.atomic():
            for user in users.order_by("pk").iterator():
                report.selected += 1
                email = str(getattr(user, email_field_name)).strip().lower()
                if email in known_emails or user.pk in linked_user_pks:
                    report.existing += 1
                    continue
                prospect = build_prospect(user)
                if prospect is None:
                    report.invalid += 1
                    continue
                known_emails.add(email)
                report.created += 1
                if self.dry_run:
                    report.unsubscribed += int(suppression_list.contains(email))
                    continue
                prospect.save()
                ProspectEvent.record(prospect, EventKind.ADDED, ACTOR_SYSTEM)
                report.unsubscribed += int(prospect.status == ProspectStatus.UNSUBSCRIBED)
        return report


def prospect_fields(user: Any) -> dict[str, Any]:
    fields = {
        "first_name": getattr(user, "first_name", "") or "",
        "last_name": getattr(user, "last_name", "") or "",
    }
    fields_hook = outreach_settings.user_prospect_fields
    if fields_hook is None:
        return fields
    hook_fields = fields_hook(user)
    unknown_names = set(hook_fields) - HOOK_FIELD_NAMES
    if unknown_names:
        raise ImproperlyConfigured(
            "OUTREACH_USER_PROSPECT_FIELDS may only return "
            f"{sorted(HOOK_FIELD_NAMES)}, not {sorted(unknown_names)}."
        )
    return {**fields, **hook_fields}


def build_prospect(user: Any) -> Prospect | None:
    """Return an unsaved prospect for the user, or ``None`` when its data does not validate."""
    email_field_name = get_user_model().get_email_field_name()
    email = str(getattr(user, email_field_name, "") or "").strip().lower()
    prospect = Prospect(email=email, **prospect_fields(user))
    try:
        prospect.full_clean(validate_unique=False)
    except ValidationError:
        return None
    return prospect


class SyncOutcome(StrEnum):
    LINKED = "linked"
    CREATED = "created"
    EXISTING = "existing"
    SKIPPED = "skipped"
    FILTERED = "filtered"


class UserProspectSyncer:
    """Syncs one new host user with the prospects, as the ``OUTREACH_SYNC_USERS`` setting asks.

    A matching prospect is linked in both modes. A prospect is created only in ``create``
    mode, for an active user the ``OUTREACH_SYNC_USERS_FILTER`` hook accepts.
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def sync(self, user: Any) -> SyncOutcome:
        email_field_name = get_user_model().get_email_field_name()
        email = str(getattr(user, email_field_name, "") or "").strip().lower()
        if not email:
            return SyncOutcome.SKIPPED
        existing_prospect = Prospect.objects.filter(email=email).first()
        if existing_prospect is not None:
            return self.link(existing_prospect)
        if self.mode != SyncUsersMode.CREATE:
            return SyncOutcome.SKIPPED
        if getattr(user, "is_active", True) is False:
            return SyncOutcome.SKIPPED
        if not self.accepts(user):
            return SyncOutcome.FILTERED
        return self.create(user, email)

    def link(self, prospect: Prospect) -> SyncOutcome:
        if prospect.user_id is not None:
            return SyncOutcome.EXISTING
        with transaction.atomic():
            linked = UserLinker().link_and_record(prospect)
        return SyncOutcome.LINKED if linked else SyncOutcome.EXISTING

    def accepts(self, user: Any) -> bool:
        user_filter = outreach_settings.sync_users_filter
        if user_filter is None:
            return True
        try:
            return bool(user_filter(user))
        except Exception:
            # INFO - the hook is host code, a failing hook must not make anyone mailable
            logger.exception("OUTREACH_SYNC_USERS_FILTER failed for user %s.", user.pk)
            return False

    def create(self, user: Any, email: str) -> SyncOutcome:
        prospect = build_prospect(user)
        if prospect is None:
            return SyncOutcome.SKIPPED
        try:
            with transaction.atomic():
                prospect.save()
                ProspectEvent.record(
                    prospect, EventKind.ADDED, ACTOR_SYSTEM, detail="user sync"
                )
        except IntegrityError:
            return SyncOutcome.EXISTING
        return SyncOutcome.CREATED
