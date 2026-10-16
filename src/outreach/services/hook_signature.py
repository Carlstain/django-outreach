import inspect
from collections.abc import Callable

from django.core.exceptions import ImproperlyConfigured

PREVIEW_PARAMETER = "preview"


def check_hook_signature(kind: str, name: str, function: Callable[..., object]) -> bool:
    """Check the function a host registers as a mail ``kind`` ("tag" or "variable").

    Returns whether the function declares the keyword-only ``preview`` parameter.

    Raises:
        ImproperlyConfigured: The function does not take the prospect first, a later parameter
            has no default, or ``preview`` is not keyword-only.
    """
    parameters = inspect.signature(function).parameters
    if not parameters:
        raise ImproperlyConfigured(
            f"The mail {kind} '{name}' must accept the prospect as its first parameter."
        )
    variadic_kinds = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    for parameter in list(parameters.values())[1:]:
        if (
            parameter.name == PREVIEW_PARAMETER
            and parameter.kind is not inspect.Parameter.KEYWORD_ONLY
        ):
            raise ImproperlyConfigured(
                f"The mail {kind} '{name}' parameter '{PREVIEW_PARAMETER}' must be "
                "keyword-only, or staff text could fill it."
            )
        if (
            parameter.default is inspect.Parameter.empty
            and parameter.kind not in variadic_kinds
        ):
            raise ImproperlyConfigured(
                f"The mail {kind} '{name}' parameter '{parameter.name}' needs a default value."
            )
    preview_parameter = parameters.get(PREVIEW_PARAMETER)
    return (
        preview_parameter is not None
        and preview_parameter.kind is inspect.Parameter.KEYWORD_ONLY
    )
