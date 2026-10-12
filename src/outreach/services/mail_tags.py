import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape

from django.core.exceptions import ImproperlyConfigured
from django.utils.html import escape

from outreach.models import Prospect

MAIL_TAG_PATTERN = re.compile(r"\{%\s*(\w+)((?:\s+(?:\"[^\"]*\"|'[^']*'|\w+))*)\s*%\}")
ARGUMENT_PATTERN = re.compile(r"\"([^\"]*)\"|'([^']*)'|(\w+)")
MAX_ARGUMENT_LENGTH = 200


@dataclass(frozen=True)
class MailTagArgument:
    text: str
    is_variable: bool


@dataclass(frozen=True)
class MailTag:
    name: str
    label: str
    example: str
    function: Callable[..., str]


class MailTagLibrary:
    def __init__(self) -> None:
        self.tags: dict[str, MailTag] = {}

    def register(
        self, *, label: str, example: str, name: str | None = None
    ) -> Callable[[Callable[..., str]], Callable[..., str]]:
        def decorator(function: Callable[..., str]) -> Callable[..., str]:
            tag_name = name or function.__name__
            if tag_name in self.tags:
                raise ImproperlyConfigured(f"The mail tag '{tag_name}' is already registered.")
            self.raise_for_required_parameters(tag_name, function)
            self.tags[tag_name] = MailTag(tag_name, label, example, function)
            return function

        return decorator

    def raise_for_required_parameters(
        self, tag_name: str, function: Callable[..., str]
    ) -> None:
        parameters = list(inspect.signature(function).parameters.values())
        if not parameters:
            raise ImproperlyConfigured(
                f"The mail tag '{tag_name}' must accept the prospect as its first parameter."
            )
        variadic_kinds = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for parameter in parameters[1:]:
            if (
                parameter.default is inspect.Parameter.empty
                and parameter.kind not in variadic_kinds
            ):
                raise ImproperlyConfigured(
                    f"The mail tag '{tag_name}' parameter '{parameter.name}' needs a default value."
                )

    def catalog(self) -> list[MailTag]:
        return sorted(self.tags.values(), key=lambda tag: tag.name)

    def parse_arguments(self, raw_arguments: str) -> list[MailTagArgument]:
        arguments = []
        for match in ARGUMENT_PATTERN.finditer(raw_arguments):
            double_quoted, single_quoted, bare_word = match.groups()
            if bare_word is not None:
                arguments.append(MailTagArgument(bare_word, is_variable=True))
            else:
                text = double_quoted if double_quoted is not None else single_quoted
                arguments.append(MailTagArgument(text, is_variable=False))
        return arguments

    def unknown_names(self, text: str) -> set[str]:
        used_names = {match.group(1) for match in MAIL_TAG_PATTERN.finditer(text)}
        return used_names - set(self.tags)

    def unknown_variables(self, text: str, allowed_keys: set[str]) -> set[str]:
        used_keys = {
            argument.text
            for match in MAIL_TAG_PATTERN.finditer(text)
            for argument in self.parse_arguments(match.group(2))
            if argument.is_variable
        }
        return used_keys - allowed_keys

    def invalid_calls(self, text: str) -> set[str]:
        invalid_names = set()
        for match in MAIL_TAG_PATTERN.finditer(text):
            tag = self.tags.get(match.group(1))
            if tag is None:
                continue
            arguments = self.parse_arguments(match.group(2))
            too_long = any(len(argument.text) > MAX_ARGUMENT_LENGTH for argument in arguments)
            try:
                inspect.signature(tag.function).bind(
                    None, *[argument.text for argument in arguments]
                )
            except TypeError:
                invalid_names.add(tag.name)
                continue
            if too_long:
                invalid_names.add(tag.name)
        return invalid_names

    def has_malformed_delimiters(self, text: str) -> bool:
        remainder = MAIL_TAG_PATTERN.sub("", text)
        return "{%" in remainder or "%}" in remainder

    def render(
        self, text: str, prospect: Prospect, values: dict[str, str], *, html: bool
    ) -> str:
        def substitute(match: re.Match[str]) -> str:
            tag = self.tags.get(match.group(1))
            if tag is None:
                return match.group(0)
            arguments = [
                self.resolve_argument(argument, values, html=html)
                for argument in self.parse_arguments(match.group(2))
            ]
            return self.format_output(str(tag.function(prospect, *arguments)), html=html)

        return MAIL_TAG_PATTERN.sub(substitute, text)

    def render_examples(self, text: str, *, html: bool) -> str:
        def substitute(match: re.Match[str]) -> str:
            tag = self.tags.get(match.group(1))
            if tag is None:
                return match.group(0)
            return self.format_output(str(tag.example), html=html)

        return MAIL_TAG_PATTERN.sub(substitute, text)

    def resolve_argument(
        self, argument: MailTagArgument, values: dict[str, str], *, html: bool
    ) -> str:
        if argument.is_variable:
            return values.get(argument.text, "")
        return unescape(argument.text) if html else argument.text

    def format_output(self, value: str, *, html: bool) -> str:
        if html:
            return escape(value)
        return value.replace("\r", " ").replace("\n", " ")


mail_tag_library = MailTagLibrary()
