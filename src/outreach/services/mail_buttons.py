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

WEB_SCHEMES = {"http", "https"}
MAILTO_SCHEME = "mailto"
BUTTON_ARGUMENT_COUNT = 2
PLACEHOLDER_LINK = "#"
TOKEN_PATTERN = re.compile(r"outreach-button-[0-9a-f]{32}-\d+")
HTML_TAG_PATTERN = re.compile(r"""<(?:[^>"']|"[^"]*"|'[^']*')*>""")
BUTTON_STYLE = (
    "display: inline-block; padding: 12px 24px; border-radius: 8px; font-weight: bold; "
    "text-decoration: none; background-color: {background}; color: {text};"
)


class InvalidButtonLink(ValueError):
    """A ``{% button %}`` has the wrong arguments, a bad link, or sits inside a tag or link."""


@dataclass(frozen=True)
class MailButton:
    label: str
    url: str


class MailButtons:
    """Handles ``{% button "Label" link %}``, a text construct that becomes a styled link."""

    def is_valid_link(self, url: str) -> bool:
        """Accept an ``http``, ``https`` (with a host) or ``mailto`` address with no spaces."""
        stripped = url.strip()
        if any(character.isspace() for character in stripped):
            return False
        parts = urlsplit(stripped)
        if parts.scheme == MAILTO_SCHEME:
            return bool(parts.path)
        return parts.scheme in WEB_SCHEMES and bool(parts.netloc)

    def markup_spans(self, html: str) -> list[tuple[int, int]]:
        return [(tag.start(), tag.end()) for tag in HTML_TAG_PATTERN.finditer(html)]

    def misplaced_button_starts(self, html: str) -> set[int]:
        spans = self.markup_spans(html)
        return {
            match.start()
            for match in MAIL_TAG_PATTERN.finditer(html)
            if match.group(1) == BUTTON_TAG_NAME
            and any(start <= match.start() < end for start, end in spans)
        }

    def has_misplaced_buttons(self, html: str) -> bool:
        return bool(self.misplaced_button_starts(html))

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
        """Swap each button for a random-nonce token and return the buttons by token.

        Args:
            resolve_argument: Turns a label or link argument into its final text.
            strict: Raise on a bad button. Otherwise use a placeholder link, for previews.

        Raises:
            InvalidButtonLink: A button is misplaced, has the wrong arguments, or has a link
                that is empty or not http, https or mailto.
        """
        nonce = uuid.uuid4().hex
        buttons: dict[str, MailButton] = {}
        misplaced_starts = self.misplaced_button_starts(html)

        def substitute(match: re.Match[str]) -> str:
            if match.group(1) != BUTTON_TAG_NAME:
                return match.group(0)
            if match.start() in misplaced_starts:
                if strict:
                    raise InvalidButtonLink(
                        "A button cannot be placed inside a tag or a link."
                    )
                return PLACEHOLDER_LINK
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
        """Replace the tokens from :meth:`extract` with styled anchors.

        Call it after the last sanitising pass, since nh3 strips ``style``.
        """
        style = BUTTON_STYLE.format(background=colors.accent, text=colors.on_accent)
        spans = self.markup_spans(html)

        def substitute(match: re.Match[str]) -> str:
            button = buttons.get(match.group(0))
            if button is None or any(start <= match.start() < end for start, end in spans):
                return match.group(0)
            return format_html(
                '<a href="{}" style="{}" rel="noopener noreferrer">{}</a>',
                button.url,
                style,
                button.label,
            )

        return TOKEN_PATTERN.sub(substitute, html)


mail_buttons = MailButtons()
