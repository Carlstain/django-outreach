from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from math import ceil

from django.db import connection, transaction
from django.db.models import Max, QuerySet
from django.utils import timezone

from outreach.choices import DeliveryStatus
from outreach.conf import outreach_settings
from outreach.models import MailingDelivery

WINDOW = timedelta(hours=1)
RELEASE_LOCK_KEY = 7_204_016


@dataclass(frozen=True)
class GateUsage:
    """How much of the hourly limit is used.

    ``free_at`` is when the next slot frees up while the limit is full, else ``None``.
    """

    limit: int
    released: int
    free_at: datetime | None

    @property
    def remaining(self) -> int:
        return max(self.limit - self.released, 0)

    @property
    def percent(self) -> int:
        return min(self.released * 100 // self.limit, 100)


@dataclass(frozen=True)
class GateForecast:
    """What a send of ``go_now + waiting`` mails would do right now."""

    go_now: int
    waiting: int
    finishes_in: timedelta | None


@dataclass(frozen=True)
class ReleaseOutcome:
    released: int
    waiting: int
    next_run_at: datetime | None


class SendGate:
    """Decides how many pending deliveries may be handed to Celery now.

    The hourly count is the number of deliveries released in the last 60 minutes, whatever
    their status, so mails released but not yet sent still count. Without the settings, or
    outside Celery mode, the gate is off and every waiting delivery is released.
    """

    @staticmethod
    def is_active() -> bool:
        return outreach_settings.send_gate_enabled

    @staticmethod
    def waiting_deliveries() -> QuerySet[MailingDelivery]:
        return MailingDelivery.objects.filter(
            status=DeliveryStatus.PENDING, released_at__isnull=True
        ).order_by("created_at", "pk")

    @staticmethod
    def recent_release_times(now: datetime) -> list[datetime]:
        return list(
            MailingDelivery.objects.filter(released_at__gt=now - WINDOW)
            .order_by("-released_at")
            .values_list("released_at", flat=True)
        )

    @classmethod
    def usage(cls, now: datetime | None = None) -> GateUsage | None:
        limit = outreach_settings.send_limit_per_hour
        if limit is None or not outreach_settings.uses_celery:
            return None
        now = now or timezone.now()
        release_times = cls.recent_release_times(now)
        free_at = release_times[limit - 1] + WINDOW if len(release_times) >= limit else None
        return GateUsage(limit=limit, released=len(release_times), free_at=free_at)

    @classmethod
    def allowance(cls, now: datetime) -> int | None:
        """How many deliveries may be released at ``now``. ``None`` means no bound."""
        if not cls.is_active():
            return None
        limit = outreach_settings.send_limit_per_hour
        delay = outreach_settings.send_delay
        limit_room = None
        if limit is not None:
            limit_room = max(limit - len(cls.recent_release_times(now)), 0)
        if delay is None:
            return limit_room
        last_release = MailingDelivery.objects.aggregate(last=Max("released_at"))["last"]
        delay_has_passed = last_release is None or last_release + delay <= now
        delay_room = 1 if delay_has_passed else 0
        return delay_room if limit_room is None else min(limit_room, delay_room)

    @classmethod
    def next_release_at(cls, now: datetime | None = None) -> datetime:
        """The earliest instant one more delivery may be released, ``now`` if one may go."""
        now = now or timezone.now()
        if not cls.is_active():
            return now
        earliest = now
        limit = outreach_settings.send_limit_per_hour
        if limit is not None:
            release_times = cls.recent_release_times(now)
            if len(release_times) >= limit:
                earliest = max(earliest, release_times[limit - 1] + WINDOW)
        delay = outreach_settings.send_delay
        if delay is not None:
            last_release = MailingDelivery.objects.aggregate(last=Max("released_at"))["last"]
            if last_release is not None:
                earliest = max(earliest, last_release + delay)
        return earliest

    @classmethod
    def forecast(cls, count: int, now: datetime | None = None) -> GateForecast:
        """Estimate how many of ``count`` new deliveries go now and how long the rest takes.

        Deliveries already waiting are released first, so they are counted ahead of the new ones.
        """
        now = now or timezone.now()
        allowance = cls.allowance(now)
        ahead = cls.waiting_deliveries().count()
        total = ahead + count
        released_now = total if allowance is None else min(total, allowance)
        go_now = max(released_now - ahead, 0)
        waiting = count - go_now
        if waiting == 0:
            return GateForecast(go_now=go_now, waiting=0, finishes_in=None)
        duration = timedelta(0)
        limit = outreach_settings.send_limit_per_hour
        if limit is not None:
            budget_left = max(limit - len(cls.recent_release_times(now)), 0)
            over_budget = max(total - budget_left, 0)
            duration = max(duration, WINDOW * ceil(over_budget / limit))
        delay = outreach_settings.send_delay
        if delay is not None:
            duration = max(duration, delay * (total - released_now))
        return GateForecast(go_now=go_now, waiting=waiting, finishes_in=duration)

    @classmethod
    def serialise_releases(cls) -> None:
        # INFO - M.E. - 21/10/26 - the lock must not depend on which rows wait: a retry can
        # make a newer row the oldest, and two runs would then not block each other
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [RELEASE_LOCK_KEY])
            return
        cls.waiting_deliveries().select_for_update().first()

    @staticmethod
    def kick() -> None:
        from outreach.tasks import release_deliveries

        transaction.on_commit(
            partial(release_deliveries.apply_async, queue=outreach_settings.celery_queue)
        )

    @classmethod
    def release_due(cls, now: datetime | None = None) -> ReleaseOutcome:
        """Hand to Celery the waiting deliveries that fit now, oldest first."""
        from outreach.services.mailing import ProspectMailer

        now = now or timezone.now()
        with transaction.atomic():
            cls.serialise_releases()
            if not cls.waiting_deliveries().exists():
                return ReleaseOutcome(released=0, waiting=0, next_run_at=None)
            allowance = cls.allowance(now)
            released_pks = list(
                cls.waiting_deliveries().values_list("pk", flat=True)[:allowance]
            )
            if released_pks:
                ProspectMailer.enqueue(released_pks, released_at=now)
        waiting = cls.waiting_deliveries().count()
        next_run_at = cls.next_release_at(now) if waiting else None
        return ReleaseOutcome(
            released=len(released_pks), waiting=waiting, next_run_at=next_run_at
        )
