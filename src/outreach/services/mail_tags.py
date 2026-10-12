import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from html import unescape

from django.core.exceptions import ImproperlyConfigured
from django.utils.html import escape

from outreach.models import Prospect
from outreach.services.variables import MailVariables

MAIL_TAG_PATTERN = re.compile(r"\{%\s*(\w+)((?:\s+(?:\"[^\"]*\"|'[^']*'|\w+))*)\s*%\}")
ARGUMENT_PATTERN = re.compile(r"\"([^\"]*)\"|'([^']*)'|(\w+)")
MAX_ARGUMENT_LENGTH = 200
BUTTON_TAG_NAME = "button"
PREVIEW_PARAMETER = "preview"


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
    accepts_preview: bool = False


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
            if tag_name == BUTTON_TAG_NAME or tag_name in MailVariables().allowed_keys():
                raise ImproperlyConfigured(f"The mail tag name '{tag_name}' is reserved.")
            self.raise_for_required_parameters(tag_name, function)
            preview_parameter = inspect.signature(function).parameters.get(PREVIEW_PARAMETER)
            accepts_preview = (
                preview_parameter is not None
                and preview_parameter.kind is inspect.Parameter.KEYWORD_ONLY
            )
            self.tags[tag_name] = MailTag(tag_name, label, example, function, accepts_preview)
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
                parameter.name == PREVIEW_PARAMETER
                and parameter.kind is not inspect.Parameter.KEYWORD_ONLY
            ):
                raise ImproperlyConfigured(
                    f"The mail tag '{tag_name}' parameter '{PREVIEW_PARAMETER}' must be "
                    "keyword-only, or staff text could fill it."
                )
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
        return used_names - set(self.tags) - {BUTTON_TAG_NAME}

    def unknown_variables(self, text: str, allowed_keys: set[str]) -> set[str]:
        used_keys = {
            argument.text
            for match in MAIL_TAG_PATTERN.finditer(text)
            for argument in self.parse_arguments(match.group(2))
            if argument.is_variable
        }
        return used_keys - allowed_keys - set(self.tags)

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

    def call(
        self, tag: MailTag, prospect: Prospect, arguments: list[str], *, preview: bool
    ) -> str:
        if tag.accepts_preview:
            return str(tag.function(prospect, *arguments, preview=preview))
        return str(tag.function(prospect, *arguments))

    def render(
        self,
        text: str,
        prospect: Prospect,
        values: dict[str, str],
        *,
        html: bool,
        preview: bool = False,
    ) -> str:
        def substitute(match: re.Match[str]) -> str:
            tag = self.tags.get(match.group(1))
            if tag is None:
                return match.group(0)
            arguments = [
                self.resolve_argument(argument, prospect, values, html=html, preview=preview)
                for argument in self.parse_arguments(match.group(2))
            ]
            output = self.call(tag, prospect, arguments, preview=preview)
            return self.format_output(output, html=html)

        return MAIL_TAG_PATTERN.sub(substitute, text)

    def render_examples(self, text: str, *, html: bool) -> str:
        def substitute(match: re.Match[str]) -> str:
            tag = self.tags.get(match.group(1))
            if tag is None:
                return match.group(0)
            return self.format_output(str(tag.example), html=html)

        return MAIL_TAG_PATTERN.sub(substitute, text)

    def resolve_argument(
        self,
        argument: MailTagArgument,
        prospect: Prospect,
        values: dict[str, str],
        *,
        html: bool,
        preview: bool = False,
    ) -> str:
        if not argument.is_variable:
            return unescape(argument.text) if html else argument.text
        if argument.text in values:
            return values[argument.text]
        tag = self.tags.get(argument.text)
        return self.call(tag, prospect, [], preview=preview) if tag else ""

    def resolve_example(self, argument: MailTagArgument, sample_values: dict[str, str]) -> str:
        if not argument.is_variable:
            return unescape(argument.text)
        if argument.text in sample_values:
            return sample_values[argument.text]
        tag = self.tags.get(argument.text)
        return str(tag.example) if tag else ""

    def format_output(self, value: str, *, html: bool) -> str:
        if html:
            return escape(value)
        return value.replace("\r", " ").replace("\n", " ")


mail_tag_library = MailTagLibrary()
