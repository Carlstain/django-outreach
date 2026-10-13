import re
from dataclasses import dataclass
from html import unescape

from django.utils.html import escape
from django.utils.translation import pgettext_lazy

from outreach.models import Prospect

VARIABLE_PATTERN = re.compile(r"\{\{\s*(\w+)\s*(?:\|\s*([^{}|]*?)\s*)?\}\}")


@dataclass(frozen=True)
class MailVariable:
    key: str
    label: str
    example: str


class MailVariables:
    """The whitelist of ``{{ variable }}`` keys usable in a mail, replaced by regex.

    A variable may carry a fallback used when its value is empty: ``{{ first_name | there }}``.
    The template engine is never involved, so staff text cannot reach a code path.
    """

    KEYS = ("first_name", "last_name", "full_name", "organization", "email", "city", "country")
    ALWAYS_ALLOWED = ("unsubscribe_url",)

    def catalog(self) -> list[MailVariable]:
        return [
            MailVariable(
                "first_name",
                pgettext_lazy("mail variable", "First name"),
                pgettext_lazy("mail variable example", "Alex"),
            ),
            MailVariable(
                "last_name",
                pgettext_lazy("mail variable", "Last name"),
                pgettext_lazy("mail variable example", "Morgan"),
            ),
            MailVariable(
                "full_name",
                pgettext_lazy("mail variable", "Full name"),
                pgettext_lazy("mail variable example", "Alex Morgan"),
            ),
            MailVariable(
                "organization",
                pgettext_lazy("mail variable", "Organization"),
                pgettext_lazy("mail variable example", "Acme Inc."),
            ),
            MailVariable(
                "email",
                pgettext_lazy("mail variable", "Email"),
                pgettext_lazy("mail variable example", "alex@example.org"),
            ),
            MailVariable(
                "city",
                pgettext_lazy("mail variable", "City"),
                pgettext_lazy("mail variable example", "Springfield"),
            ),
            MailVariable(
                "country",
                pgettext_lazy("mail variable", "Country"),
                pgettext_lazy("mail variable example", "United Kingdom"),
            ),
        ]

    def values_for(self, prospect: Prospect) -> dict[str, str]:
        """Return the value of each key for a prospect.

        Names fall back to the linked user's when the prospect's are empty.
        """
        user = prospect.user
        first_name = prospect.first_name or (getattr(user, "first_name", "") if user else "")
        last_name = prospect.last_name or (getattr(user, "last_name", "") if user else "")
        return {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": f"{first_name} {last_name}".strip(),
            "organization": prospect.organization,
            "email": prospect.email,
            "city": prospect.city,
            "country": prospect.country,
        }

    def allowed_keys(self) -> set[str]:
        return set(self.KEYS) | set(self.ALWAYS_ALLOWED)

    def used_keys(self, text: str) -> set[str]:
        return {match.group(1) for match in VARIABLE_PATTERN.finditer(text)}

    def unknown_keys(self, text: str) -> set[str]:
        return self.used_keys(text) - self.allowed_keys()

    def has_malformed_braces(self, text: str) -> bool:
        remainder = VARIABLE_PATTERN.sub("", text)
        return "{{" in remainder or "}}" in remainder

    def render(self, text: str, values: dict[str, str], *, html: bool) -> str:
        def substitute(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in values:
                return match.group(0)
            value = values[key]
            if not value:
                fallback = match.group(2) or ""
                value = unescape(fallback) if html else fallback
            if html:
                return escape(value)
            return value.replace("\r", " ").replace("\n", " ")

        return VARIABLE_PATTERN.sub(substitute, text)
