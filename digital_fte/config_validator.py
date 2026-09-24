"""Schema validation for Digital FTE configuration dictionaries.

A run is configured from a plain ``dict`` (parsed JSON, a TOML table, keyword
overrides). This module checks such a dict against a small declarative schema
of :class:`FieldSpec` entries: which keys are required, the expected type of
each, optional numeric ``min``/``max`` bounds, an optional ``choices`` set, and
a ``default`` for absent optional keys.

Validation is pure and collects *all* problems rather than stopping at the
first, so a misconfigured run surfaces every error at once.
:func:`check_config` returns a :class:`ValidationResult`; :func:`validate_config`
is the raising counterpart that returns the normalised values or raises
:class:`ConfigValidationError` carrying the full list.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class ConfigValidationError(Exception):
    """Raised by :func:`validate_config` when a config fails its schema.

    :attr:`errors` is the tuple of human-readable problem descriptions.
    """

    def __init__(self, errors: tuple[str, ...]) -> None:
        super().__init__("; ".join(errors) or "config validation failed")
        self.errors = errors


@dataclass(frozen=True)
class FieldSpec:
    """Declarative rules for a single config key.

    Attributes:
        type: The expected Python type (e.g. ``int``, ``str``, ``bool``).
        required: Whether the key must be present.
        min: Optional inclusive lower bound (numeric types only).
        max: Optional inclusive upper bound (numeric types only).
        choices: Optional collection of permitted values.
        default: Value substituted for an absent optional key.
    """

    type: type
    required: bool = True
    min: float | None = None
    max: float | None = None
    choices: tuple[Any, ...] | None = None
    default: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.type, type):
            raise TypeError("FieldSpec.type must be a type")


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of checking a config against a schema.

    Attributes:
        ok: ``True`` when no errors were found.
        values: The normalised config (defaults applied) -- only meaningful
            when ``ok`` is ``True``.
        errors: Human-readable descriptions of every problem found.
    """

    ok: bool
    values: Mapping[str, Any]
    errors: tuple[str, ...] = field(default_factory=tuple)


def _type_name(tp: type) -> str:
    return getattr(tp, "__name__", str(tp))


def _check_field(key: str, value: Any, spec: FieldSpec) -> list[str]:
    errors: list[str] = []

    # bool is a subclass of int; only accept it when explicitly expected.
    if isinstance(value, bool) and spec.type is not bool:
        errors.append(f"{key!r} must be {_type_name(spec.type)}, got bool")
        return errors
    if not isinstance(value, spec.type):
        errors.append(
            f"{key!r} must be {_type_name(spec.type)}, "
            f"got {_type_name(type(value))}"
        )
        return errors

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if spec.min is not None and value < spec.min:
            errors.append(f"{key!r} must be >= {spec.min}, got {value}")
        if spec.max is not None and value > spec.max:
            errors.append(f"{key!r} must be <= {spec.max}, got {value}")

    if spec.choices is not None and value not in spec.choices:
        errors.append(f"{key!r} must be one of {list(spec.choices)}, got {value!r}")

    return errors


def check_config(
    config: Mapping[str, Any], schema: Mapping[str, FieldSpec]
) -> ValidationResult:
    """Validate ``config`` against ``schema`` without raising.

    Args:
        config: The configuration mapping to check.
        schema: A mapping of key name to :class:`FieldSpec`.

    Returns:
        A :class:`ValidationResult`. When ``ok`` is ``True`` its ``values``
        holds the config restricted to schema keys with defaults filled in for
        absent optional keys.

    Raises:
        TypeError: If ``config`` or ``schema`` is not a mapping, or a schema
            value is not a :class:`FieldSpec`.
    """
    if not isinstance(config, Mapping):
        raise TypeError("config must be a mapping")
    if not isinstance(schema, Mapping):
        raise TypeError("schema must be a mapping")

    errors: list[str] = []
    values: dict[str, Any] = {}

    for key, spec in schema.items():
        if not isinstance(spec, FieldSpec):
            raise TypeError(f"schema[{key!r}] must be a FieldSpec")

        if key not in config:
            if spec.required:
                errors.append(f"missing required key {key!r}")
            else:
                values[key] = spec.default
            continue

        value = config[key]
        field_errors = _check_field(key, value, spec)
        if field_errors:
            errors.extend(field_errors)
        else:
            values[key] = value

    if errors:
        return ValidationResult(ok=False, values={}, errors=tuple(errors))
    return ValidationResult(ok=True, values=values, errors=())


def validate_config(
    config: Mapping[str, Any], schema: Mapping[str, FieldSpec]
) -> dict[str, Any]:
    """Validate ``config`` and return normalised values, or raise.

    Raises:
        ConfigValidationError: If any field is missing or invalid; the
            exception's ``errors`` lists every problem.
        TypeError: For the same structural problems as :func:`check_config`.
    """
    result = check_config(config, schema)
    if not result.ok:
        raise ConfigValidationError(result.errors)
    return dict(result.values)
