from datetime import datetime

from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import pgettext_lazy

from outreach.models import Prospect
from outreach.services.mail_tags import mail_tag_library

MIDDAY_HOUR = 12
EVENING_HOUR = 18


def to_local(moment: datetime) -> datetime:
    return timezone.localtime(moment) if timezone.is_aware(moment) else moment


@mail_tag_library.register(
    label=pgettext_lazy("mail tag", "Today's date"),
    example=pgettext_lazy("mail tag example", "May 14, 2026"),
)
def today(prospect: Prospect, format: str = "DATE_FORMAT") -> str:
    """Today's date; the optional argument is a Django date format name or format string."""
    return date_format(to_local(timezone.now()), format)


@mail_tag_library.register(
    label=pgettext_lazy("mail tag", "Greeting for the time of day"),
    example=pgettext_lazy("mail tag example", "Good morning"),
)
def greeting(prospect: Prospect) -> str:
    """Good morning before noon, good afternoon before 18:00, good evening after."""
    hour = to_local(timezone.now()).hour
    if hour < MIDDAY_HOUR:
        return str(pgettext_lazy("mail tag greeting", "Good morning"))
    if hour < EVENING_HOUR:
        return str(pgettext_lazy("mail tag greeting", "Good afternoon"))
    return str(pgettext_lazy("mail tag greeting", "Good evening"))


@mail_tag_library.register(
    label=pgettext_lazy("mail tag", "Date the member joined"),
    example=pgettext_lazy("mail tag example", "March 2, 2024"),
)
def member_since(prospect: Prospect, format: str = "DATE_FORMAT") -> str:
    """Date the linked user joined; empty for a prospect with no linked user."""
    joined_at = getattr(prospect.user, "date_joined", None)
    if joined_at is None:
        return ""
    return date_format(to_local(joined_at), format)
