"""Typed parsing of environment-variable mappings for a Digital FTE run.

Environment variables arrive as strings; the runtime wants typed values with
sensible defaults. This module parses a ``{name: str}`` mapping against a spec
of :class:`EnvVar` entries, coercing each value to ``int``, ``float``, ``bool``,
or ``str`` and applying a default when a variable is absent.

Parsing is pure -- the ``env`` mapping is passed in rather than read from
``os.environ`` -- so a run's configuration is reproducible and testable. A
missing required variable, or a value that will not coerce to its declared
type, raises :class:`EnvParseError` rather than silently defaulting.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_VALID_TYPES = ("int", "float", "bool", "str")

# Recognised boolean spellings, compared case-insensitively after stripping.
_TRUE = frozenset({"1", "true", "yes", "on", "y", "t"})
_FALSE = frozenset({"0", "false", "no", "off", "n", "f"})


class _Missing:
    """Sentinel marking "no default supplied" (distinct from ``None``)."""

    _instance: "_Missing | None" = None

    def __new__(cls) -> "_Missing":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "<MISSING>"


MISSING = _Missing()


class EnvParseError(Exception):
    """Raised when a required var is absent or a value fails to coerce."""


@dataclass(frozen=True)
class EnvVar:
    """The parsing rule for one environment variable.

    Attributes:
        type: One of ``"int"``, ``"float"``, ``"bool"``, ``"str"``.
        default: Value used when the variable is absent. Leave as
            :data:`MISSING` to make the variable required.
        required: Force the variable to be present even if a default is set.
    """

    type: str
    default: Any = MISSING
    required: bool = False

    def __post_init__(self) -> None:
        if self.type not in _VALID_TYPES:
            raise ValueError(f"type must be one of {_VALID_TYPES}, got {self.type!r}")


def _coerce(name: str, raw: str, type_name: str) -> Any:
    if type_name == "str":
        return raw
    text = raw.strip()
    if type_name == "int":
        try:
            return int(text)
        except ValueError:
            raise EnvParseError(f"{name}={raw!r} is not a valid int") from None
    if type_name == "float":
        try:
            number = float(text)
        except ValueError:
            raise EnvParseError(f"{name}={raw!r} is not a valid float") from None
        if math.isnan(number) or math.isinf(number):
            raise EnvParseError(f"{name}={raw!r} must be a finite float")
        return number
    # bool
    lowered = text.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise EnvParseError(f"{name}={raw!r} is not a valid bool")


def parse_env(
    env: Mapping[str, str], spec: Mapping[str, EnvVar]
) -> dict[str, Any]:
    """Parse ``env`` into typed values per ``spec``.

    Args:
        env: The raw environment mapping of ``name -> string``.
        spec: A mapping of variable name to :class:`EnvVar`.

    Returns:
        A dict mapping each spec key to its coerced value (or default). Absent
        optional variables with no default are omitted from the result.

    Raises:
        TypeError: If ``env`` or ``spec`` is not a mapping, a spec value is not
            an :class:`EnvVar`, or a present raw value is not a string.
        EnvParseError: If a required variable is missing or a value fails to
            coerce to its declared type.
    """
    if not isinstance(env, Mapping):
        raise TypeError("env must be a mapping")
    if not isinstance(spec, Mapping):
        raise TypeError("spec must be a mapping")

    result: dict[str, Any] = {}
    for name, var in spec.items():
        if not isinstance(var, EnvVar):
            raise TypeError(f"spec[{name!r}] must be an EnvVar")

        if name not in env:
            if var.required:
                raise EnvParseError(f"missing required env var {name!r}")
            if var.default is not MISSING:
                result[name] = var.default
            continue

        raw = env[name]
        if not isinstance(raw, str):
            raise TypeError(f"env[{name!r}] must be a string")
        result[name] = _coerce(name, raw, var.type)

    return result
