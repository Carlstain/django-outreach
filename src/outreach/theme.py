import logging
import re
from dataclasses import dataclass
from functools import cached_property

from django.conf import settings

COLOR_KEYS = (
    "brand",
    "accent",
    "on_accent",
    "text",
    "muted",
    "background",
    "surface",
    "border",
)
OPTIONAL_COLOR_KEYS = ("avatar",)
THEME_KEYS = COLOR_KEYS + OPTIONAL_COLOR_KEYS + ("font_family", "dark")

DEFAULT_LIGHT = {
    "brand": "#2a2124",
    "accent": "#7a3b69",
    "on_accent": "#ffffff",
    "text": "#2a2124",
    "muted": "#75676b",
    "background": "#f8f4f4",
    "surface": "#fffcfc",
    "border": "#e8dedf",
}
DEFAULT_DARK = {
    "brand": "#f0e7ea",
    "accent": "#d79bc6",
    "on_accent": "#240c1d",
    "text": "#f0e7ea",
    "muted": "#aa9aa1",
    "background": "#181316",
    "surface": "#231c20",
    "border": "#3b2f35",
}
SYSTEM_FONT_STACK = (
    "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
)

CSS_VARIABLES = {
    "brand": "--brand",
    "accent": "--accent",
    "on_accent": "--on-accent",
    "text": "--fg",
    "muted": "--muted",
    "background": "--bg",
    "surface": "--surface",
    "border": "--line",
    "avatar": "--avatar-bg",
}

COLOR_MAX_LENGTH = 100
FONT_FAMILY_MAX_LENGTH = 200
COLOR_ARGUMENT = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:deg|rad|grad|turn|%)?"
COLOR_PATTERNS = (
    re.compile(r"#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})", re.IGNORECASE),
    re.compile(
        rf"(?:rgb|rgba|hsl|hsla)\(\s*{COLOR_ARGUMENT}"
        rf"(?:(?:\s*[,/]\s*|\s+){COLOR_ARGUMENT}){{2,3}}\s*\)",
        re.IGNORECASE,
    ),
    re.compile(r"[a-zA-Z]{3,20}"),
)
FONT_BARE_FAMILY = r"-?[A-Za-z][A-Za-z0-9 _.-]*"
FONT_SINGLE_QUOTED = r"'[^<>;{}'\\\r\n]+'"
FONT_DOUBLE_QUOTED = r'"[^<>;{}"\\\r\n]+"'
FONT_ITEM = rf"(?:{FONT_BARE_FAMILY}|{FONT_SINGLE_QUOTED}|{FONT_DOUBLE_QUOTED})"
FONT_FAMILY_PATTERN = re.compile(rf" *{FONT_ITEM}(?: *, *{FONT_ITEM})* *")

logger = logging.getLogger("outreach")
warned_problems: set[str] = set()


@dataclass(frozen=True)
class EmailColors:
    background: str
    card: str
    border: str
    text: str
    muted: str
    brand: str
    accent: str
    on_accent: str


@dataclass(frozen=True)
class ResolvedTheme:
    light: dict[str, str]
    dark: dict[str, str]
    font_family: str
    email: EmailColors


def is_valid_color(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= COLOR_MAX_LENGTH
        and any(pattern.fullmatch(value) for pattern in COLOR_PATTERNS)
    )


def is_valid_font_family(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= FONT_FAMILY_MAX_LENGTH
        and FONT_FAMILY_PATTERN.fullmatch(value) is not None
    )


class OutreachTheme:
    def configured(self) -> object:
        return getattr(settings, "OUTREACH_THEME", None) or {}

    def errors(self) -> list[str]:
        configured = self.configured()
        if not isinstance(configured, dict):
            return ["OUTREACH_THEME must be a dict."]
        errors = self.palette_errors(configured, "OUTREACH_THEME", allow_font_and_dark=True)
        if "dark" in configured:
            dark = configured["dark"]
            if isinstance(dark, dict):
                errors += self.palette_errors(
                    dark, "OUTREACH_THEME['dark']", allow_font_and_dark=False
                )
            else:
                errors.append("OUTREACH_THEME['dark'] must be a dict.")
        return errors

    def palette_errors(
        self, palette: dict, location: str, *, allow_font_and_dark: bool
    ) -> list[str]:
        allowed_keys = set(COLOR_KEYS + OPTIONAL_COLOR_KEYS)
        if allow_font_and_dark:
            allowed_keys |= {"font_family", "dark"}
        errors = []
        for key, value in palette.items():
            if key not in allowed_keys:
                errors.append(f"{location} has an unknown key: {key!r}.")
            elif key == "dark":
                continue
            elif key == "font_family":
                if value is not None and not is_valid_font_family(value):
                    errors.append(f"{location}['font_family'] is not a valid font stack.")
            elif value is not None and not is_valid_color(value):
                errors.append(f"{location}[{key!r}] is not a valid CSS color.")
        return errors

    def warn_once(self, problem: str) -> None:
        if problem not in warned_problems:
            warned_problems.add(problem)
            logger.warning("%s The default is used instead.", problem)

    def valid_colors(self, palette: object, location: str) -> dict[str, str]:
        if not isinstance(palette, dict):
            self.warn_once(f"{location} must be a dict.")
            return {}
        valid = {}
        for key in COLOR_KEYS + OPTIONAL_COLOR_KEYS:
            value = palette.get(key)
            if value is None:
                continue
            if is_valid_color(value):
                valid[key] = value
            else:
                self.warn_once(f"{location}[{key!r}] is not a valid CSS color.")
        return valid

    def resolve(self) -> ResolvedTheme:
        configured = self.configured()
        if not isinstance(configured, dict):
            self.warn_once("OUTREACH_THEME must be a dict.")
            configured = {}
        for key in configured:
            if key not in THEME_KEYS:
                self.warn_once(f"OUTREACH_THEME has an unknown key: {key!r}.")
        light = {**DEFAULT_LIGHT, **self.valid_colors(configured, "OUTREACH_THEME")}
        dark_configured = configured.get("dark") or {}
        dark = {**DEFAULT_DARK, **self.valid_colors(dark_configured, "OUTREACH_THEME['dark']")}
        font_family = configured.get("font_family")
        if font_family is not None and not is_valid_font_family(font_family):
            self.warn_once("OUTREACH_THEME['font_family'] is not a valid font stack.")
            font_family = None
        email = EmailColors(
            background=light["background"],
            card=light["surface"],
            border=light["border"],
            text=light["text"],
            muted=light["muted"],
            brand=light["brand"],
            accent=light["accent"],
            on_accent=light["on_accent"],
        )
        return ResolvedTheme(light, dark, font_family or SYSTEM_FONT_STACK, email)

    @cached_property
    def resolved(self) -> ResolvedTheme:
        return self.resolve()

    def light(self) -> dict[str, str]:
        return dict(self.resolved.light)

    def dark(self) -> dict[str, str]:
        return dict(self.resolved.dark)

    def font_family(self) -> str:
        return self.resolved.font_family

    def declarations(self, palette: dict[str, str]) -> str:
        return "".join(f"{CSS_VARIABLES[key]}:{value};" for key, value in palette.items())

    def css(self) -> str:
        resolved = self.resolved
        light_declarations = self.declarations(resolved.light)
        dark_declarations = self.declarations(resolved.dark)
        font_declaration = f"--font-ui:{resolved.font_family};"
        return (
            f":root{{color-scheme:light dark;{light_declarations}{font_declaration}}}"
            f"@media (prefers-color-scheme: dark){{:root{{{dark_declarations}}}}}"
        )

    @property
    def email(self) -> EmailColors:
        return self.resolved.email
