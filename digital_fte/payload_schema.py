"""JSON-schema-style validation for task payloads.

Task intake often receives loosely-typed ``dict`` payloads (for example from a
JSON file or an HTTP body).  Before such a payload is handed to the reasoning
loop it is worth checking that required fields are present, that values have the
expected types, and that numeric/length constraints hold.  This module provides
a small, dependency-free validator in the dataclass + explicit-validation style
used elsewhere in the package.

The validator returns a tuple of :class:`FieldError` objects (empty when the
payload is valid) rather than raising, so callers can report every problem at
once instead of failing on the first.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Recognised logical types mapped to the concrete Python types accepted for them.
# ``bool`` is deliberately excluded from the numeric types: in Python ``True`` is
# an ``int`` instance, but treating a boolean as a number is almost never what a
# schema author intends.
_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list, tuple),
    "object": (dict,),
}


@dataclass(frozen=True)
class FieldSpec:
    """Constraints for a single payload field.

    Only the constraints relevant to a field's ``type`` are honoured:
    ``minimum``/``maximum`` apply to ``integer``/``number``; ``min_length``/
    ``max_length`` apply to ``string``/``array``; ``pattern`` applies to
    ``string``; ``choices`` applies to any type.
    """

    type: str
    required: bool = True
    minimum: float | None = None
    maximum: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    choices: tuple[object, ...] | None = None

    def __post_init__(self) -> None:
        if self.type not in _TYPE_MAP:
            raise ValueError(f"unknown field type: {self.type!r}")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("minimum cannot exceed maximum")
        if self.min_length is not None and self.min_length < 0:
            raise ValueError("min_length cannot be negative")
        if self.max_length is not None and self.max_length < 0:
            raise ValueError("max_length cannot be negative")
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("min_length cannot exceed max_length")
        if self.pattern is not None:
            re.compile(self.pattern)  # fail fast on an invalid regex


@dataclass(frozen=True)
class FieldError:
    """A single, structured validation failure."""

    field: str
    code: str
    message: str


@dataclass(frozen=True)
class Schema:
    """A named collection of :class:`FieldSpec` constraints.

    ``allow_unknown`` controls whether payload keys with no matching spec are
    tolerated (``True``) or reported as ``unknown_field`` errors (``False``).
    """

    fields: dict[str, FieldSpec]
    allow_unknown: bool = True
    _order: tuple[str, ...] = field(default_factory=tuple, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.fields, dict) or not self.fields:
            raise ValueError("schema requires a non-empty mapping of fields")
        for name, spec in self.fields.items():
            if not isinstance(name, str) or not name:
                raise ValueError("field names must be non-empty strings")
            if not isinstance(spec, FieldSpec):
                raise TypeError(f"spec for {name!r} must be a FieldSpec")
        # Preserve declaration order for deterministic error reporting even if a
        # caller later mutates the mapping's iteration order.
        object.__setattr__(self, "_order", tuple(self.fields))


def _check_value(name: str, spec: FieldSpec, value: object) -> list[FieldError]:
    """Validate a present (non-missing) value against its spec."""
    errors: list[FieldError] = []
    accepted = _TYPE_MAP[spec.type]

    # ``bool`` masquerades as ``int``; reject it for numeric specs explicitly.
    is_bool = isinstance(value, bool)
    numeric = spec.type in ("integer", "number")
    if not isinstance(value, accepted) or (numeric and is_bool):
        errors.append(
            FieldError(
                name,
                "type",
                f"expected {spec.type}, got {type(value).__name__}",
            )
        )
        # Type is wrong: constraint checks below would be meaningless/erroring.
        return errors

    if numeric:
        if spec.minimum is not None and value < spec.minimum:
            errors.append(
                FieldError(name, "minimum", f"must be >= {spec.minimum}")
            )
        if spec.maximum is not None and value > spec.maximum:
            errors.append(
                FieldError(name, "maximum", f"must be <= {spec.maximum}")
            )

    if spec.type in ("string", "array"):
        length = len(value)  # type: ignore[arg-type]
        if spec.min_length is not None and length < spec.min_length:
            errors.append(
                FieldError(
                    name, "min_length", f"length must be >= {spec.min_length}"
                )
            )
        if spec.max_length is not None and length > spec.max_length:
            errors.append(
                FieldError(
                    name, "max_length", f"length must be <= {spec.max_length}"
                )
            )

    if (
        spec.type == "string"
        and spec.pattern is not None
        and re.fullmatch(spec.pattern, value) is None  # type: ignore[arg-type]
    ):
        errors.append(
            FieldError(name, "pattern", f"must match /{spec.pattern}/")
        )

    if spec.choices is not None and value not in spec.choices:
        allowed = ", ".join(repr(c) for c in spec.choices)
        errors.append(FieldError(name, "choice", f"must be one of: {allowed}"))

    return errors


def validate_payload(payload: object, schema: Schema) -> tuple[FieldError, ...]:
    """Validate ``payload`` against ``schema``.

    Returns a tuple of :class:`FieldError` describing every problem found, in a
    stable order (schema-declaration order first, then any unknown keys sorted
    alphabetically).  An empty tuple means the payload is valid.

    A payload that is not a ``dict`` yields a single ``not_an_object`` error.
    """
    if not isinstance(payload, dict):
        return (
            FieldError(
                "", "not_an_object",
                f"payload must be an object, got {type(payload).__name__}",
            ),
        )

    errors: list[FieldError] = []
    for name in schema._order:
        spec = schema.fields[name]
        if name not in payload:
            if spec.required:
                errors.append(
                    FieldError(name, "missing", "required field is missing")
                )
            continue
        errors.extend(_check_value(name, spec, payload[name]))

    if not schema.allow_unknown:
        for name in sorted(set(payload) - set(schema.fields)):
            errors.append(
                FieldError(str(name), "unknown_field", "field is not permitted")
            )

    return tuple(errors)


def is_valid_payload(payload: object, schema: Schema) -> bool:
    """Return ``True`` when ``payload`` satisfies ``schema``."""
    return not validate_payload(payload, schema)
