import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured

from outreach.models import Prospect
from outreach.services.hook_signature import check_hook_signature

VARIABLE_NAME_PATTERN = re.compile(r"\w+")


@dataclass(frozen=True)
class HostVariable:
    name: str
    label: str
    example: str
    function: Callable[..., object]
    accepts_preview: bool = False

    def value_for(self, prospect: Prospect, *, preview: bool) -> str:
        result = (
            self.function(prospect, preview=preview)
            if self.accepts_preview
            else self.function(prospect)
        )
        return "" if result is None else str(result)


class MailVariableLibrary:
    """Registry of the variables a host adds, usable as ``{{ name | fallback }}``.

    Use the shared ``mail_variable_library`` instance and register variables in a
    ``mail_variables.py`` module of an installed app, where they are autodiscovered.
    """

    def __init__(self) -> None:
        self.variables: dict[str, HostVariable] = {}

    def register(
        self, *, label: str, example: str, name: str | None = None
    ) -> Callable[[Callable[..., object]], Callable[..., object]]:
        """Register a function as a mail variable.

        The function receives the prospect and returns the text to write. ``None`` or an empty
        text takes the fallback of the variable. It runs only when a message uses the variable.
        A keyword-only ``preview`` parameter with a default receives ``True`` while a message is
        only previewed or tested.

        Raises:
            ImproperlyConfigured: The name is not a word, is already registered, is a built-in
                variable, ``button`` or a tag, or the signature of the function is not valid.
        """

        def decorator(function: Callable[..., object]) -> Callable[..., object]:
            # INFO - M.E. - 17/10/26 - imported here because both modules import this one
            from outreach.services.mail_tags import BUTTON_TAG_NAME, mail_tag_library
            from outreach.services.variables import MailVariables

            variable_name = name or function.__name__
            if not VARIABLE_NAME_PATTERN.fullmatch(variable_name):
                raise ImproperlyConfigured(
                    f"The mail variable name '{variable_name}' must be letters, digits or _."
                )
            if variable_name in self.variables:
                raise ImproperlyConfigured(
                    f"The mail variable '{variable_name}' is already registered."
                )
            reserved_names = {
                BUTTON_TAG_NAME,
                *MailVariables().allowed_keys(),
                *mail_tag_library.tags,
            }
            if variable_name in reserved_names:
                raise ImproperlyConfigured(
                    f"The mail variable name '{variable_name}' is reserved."
                )
            accepts_preview = check_hook_signature("variable", variable_name, function)
            self.variables[variable_name] = HostVariable(
                variable_name, label, example, function, accepts_preview
            )
            return function

        return decorator

    def catalog(self) -> list[HostVariable]:
        """Return the registered variables sorted by name."""
        return sorted(self.variables.values(), key=lambda variable: variable.name)


class HostVariableValues(Mapping[str, str]):
    """The values of the variables for one prospect, host variables computed when first read."""

    def __init__(
        self,
        fixed: Mapping[str, str],
        library: MailVariableLibrary,
        prospect: Prospect,
        preview: bool,
    ) -> None:
        self.fixed = fixed
        self.library = library
        self.prospect = prospect
        self.preview = preview
        self.computed: dict[str, str] = {}

    def __getitem__(self, key: str) -> str:
        if key in self.fixed:
            return self.fixed[key]
        variable = self.library.variables.get(key)
        if variable is None:
            raise KeyError(key)
        if key not in self.computed:
            self.computed[key] = variable.value_for(self.prospect, preview=self.preview)
        return self.computed[key]

    def __contains__(self, key: object) -> bool:
        return key in self.fixed or key in self.library.variables

    def __iter__(self) -> Iterator[str]:
        # INFO - M.E. - 17/10/26 - listing every key, as dict(values) does, runs every host
        # function for the recipient. Rendering only uses `in` and `[]`.
        yield from self.fixed
        yield from self.library.variables

    def __len__(self) -> int:
        return len(self.fixed) + len(self.library.variables)


mail_variable_library = MailVariableLibrary()
