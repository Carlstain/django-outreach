from django.contrib.auth.base_user import AbstractBaseUser
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from outreach.choices import EventKind
from outreach.models import Audience, Prospect, ProspectEvent


class AudienceNameTaken(Exception):
    """An audience with that name (ignoring case) exists."""


class AudienceCreator:
    def create(self, name: str, creator: AbstractBaseUser | None) -> Audience:
        """Create an audience and record who created it.

        Raises:
            AudienceNameTaken: The name is taken, ignoring case.
        """
        try:
            with transaction.atomic():
                return Audience.objects.create(
                    name=name, created_by=creator, updated_by=creator
                )
        except IntegrityError as error:
            raise AudienceNameTaken(name) from error


class AudienceMembers:
    """Adds prospects to an audience and removes them, keeping a history of each change."""

    def add(self, audience: Audience, prospects: QuerySet[Prospect], actor: str) -> int:
        """Add the prospects that are not members yet and return how many were added."""
        with transaction.atomic():
            new_member_pks = list(
                prospects.exclude(audiences=audience).values_list("pk", flat=True)
            )
            audience.prospects.add(*new_member_pks)
            ProspectEvent.record_many(
                new_member_pks, EventKind.AUDIENCE_ADDED, actor, audience.name
            )
        return len(new_member_pks)

    def remove(self, audience: Audience, prospects: QuerySet[Prospect], actor: str) -> int:
        """Remove the prospects that are members and return how many were removed."""
        with transaction.atomic():
            former_member_pks = list(
                prospects.filter(audiences=audience).values_list("pk", flat=True)
            )
            Prospect.audiences.through.objects.filter(
                audience=audience, prospect__in=prospects.values("pk")
            ).delete()
            ProspectEvent.record_many(
                former_member_pks, EventKind.AUDIENCE_REMOVED, actor, audience.name
            )
        return len(former_member_pks)
