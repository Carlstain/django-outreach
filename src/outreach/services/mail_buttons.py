import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.utils.html import format_html

from outreach.services.mail_tags import (
    BUTTON_TAG_NAME,
    MAIL_TAG_PATTERN,
    MailTagArgument,
    mail_tag_library,
)
from outreach.theme import EmailColors

BUTTON_SCHEMES = {"http", "https", "mailto"}
BUTTON_ARGUMENT_COUNT = 2
PLACEHOLDER_LINK = "#"
TOKEN_PATTERN = re.compile(r"outreach-button-[0-9a-f]{32}-\d+")
BUTTON_STYLE = (
    "display: inline-block; padding: 12px 24px; border-radius: 8px; font-weight: bold; "
    "text-decoration: none; background-color: {background}; color: {text};"
)


class InvalidButtonLink(ValueError):
    pass


@dataclass(frozen=True)
class MailButton:
    label: str
    url: str


class MailButtons:
    def is_valid_link(self, url: str) -> bool:
        parts = urlsplit(url.strip())
        return parts.scheme in BUTTON_SCHEMES and bool(parts.netloc or parts.path)

    def contains_button(self, text: str) -> bool:
        return any(
            match.group(1) == BUTTON_TAG_NAME for match in MAIL_TAG_PATTERN.finditer(text)
        )

    def has_invalid_buttons(self, text: str) -> bool:
        for match in MAIL_TAG_PATTERN.finditer(text):
            if match.group(1) != BUTTON_TAG_NAME:
                continue
            arguments = mail_tag_library.parse_arguments(match.group(2))
            if len(arguments) != BUTTON_ARGUMENT_COUNT:
                return True
            label, link = arguments
            if not label.is_variable and not label.text.strip():
                return True
            if not link.is_variable and not self.is_valid_link(link.text):
                return True
        return False

    def extract(
        self,
        html: str,
        resolve_argument: Callable[[MailTagArgument], str],
        *,
        strict: bool = True,
    ) -> tuple[str, dict[str, MailButton]]:
        nonce = uuid.uuid4().hex
        buttons: dict[str, MailButton] = {}

        def substitute(match: re.Match[str]) -> str:
            if match.group(1) != BUTTON_TAG_NAME:
                return match.group(0)
            arguments = mail_tag_library.parse_arguments(match.group(2))
            if len(arguments) != BUTTON_ARGUMENT_COUNT:
                raise InvalidButtonLink("A button needs a label and one link.")
            label, url = (resolve_argument(argument) for argument in arguments)
            if not self.is_valid_link(url):
                if strict:
                    raise InvalidButtonLink(
                        f"The link of the button '{label}' is empty or is not an http, https "
                        "or mailto address."
                    )
                url = PLACEHOLDER_LINK
            token = f"outreach-button-{nonce}-{len(buttons)}"
            buttons[token] = MailButton(label, url.strip())
            return token

        return MAIL_TAG_PATTERN.sub(substitute, html), buttons

    def insert(self, html: str, buttons: dict[str, MailButton], colors: EmailColors) -> str:
        style = BUTTON_STYLE.format(background=colors.accent, text=colors.on_accent)

        def substitute(match: re.Match[str]) -> str:
            button = buttons.get(match.group(0))
            if button is None:
                return match.group(0)
            return format_html(
                '<a href="{}" style="{}" rel="noopener noreferrer">{}</a>',
                button.url,
                style,
                button.label,
            )

        return TOKEN_PATTERN.sub(substitute, html)


mail_buttons = MailButtons()
