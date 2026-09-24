"""Map errors to a small, stable taxonomy of categories.

Where :mod:`digital_fte.retry_classifier` answers *should I retry?*, this module
answers *what kind of failure was this?* -- routing an error into one of a
fixed set of categories so telemetry can aggregate failures and dashboards can
group them:

* ``network``    -- connectivity, timeouts, DNS, broken pipes;
* ``auth``       -- authentication/authorisation failures;
* ``rate_limit`` -- throttling / too-many-requests;
* ``validation`` -- bad input, schema/type/value problems;
* ``unknown``    -- nothing matched.

Categorisation is a pure function of the exception's type name and message,
checked in a fixed priority order so the result is deterministic. No clock, no
randomness.
"""
from __future__ import annotations

from dataclasses import dataclass

NETWORK = "network"
AUTH = "auth"
RATE_LIMIT = "rate_limit"
VALIDATION = "validation"
UNKNOWN = "unknown"

CATEGORIES = (NETWORK, AUTH, RATE_LIMIT, VALIDATION, UNKNOWN)

# Ordered (category, hints) rules. Rate-limit is checked before network/auth so
# that a "429 too many requests" is not swallowed by a generic auth/HTTP hint.
_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        RATE_LIMIT,
        ("ratelimit", "rate limit", "throttl", "too many requests", "429", "quota exceeded"),
    ),
    (
        AUTH,
        (
            "auth",
            "unauthorized",
            "unauthorised",
            "forbidden",
            "permission",
            "credential",
            "token expired",
            "invalid token",
            "access denied",
            "401",
            "403",
        ),
    ),
    (
        NETWORK,
        (
            "timeout",
            "timed out",
            "connection",
            "connectionreset",
            "connectionrefused",
            "brokenpipe",
            "broken pipe",
            "dns",
            "socket",
            "unreachable",
            "network",
            "502",
            "503",
            "504",
        ),
    ),
    (
        VALIDATION,
        (
            "validation",
            "valueerror",
            "typeerror",
            "keyerror",
            "schema",
            "invalid",
            "malformed",
            "required",
            "missing field",
            "assertion",
            "400",
            "422",
        ),
    ),
)


@dataclass(frozen=True)
class CategorizedError:
    """An error's assigned category plus the signal that decided it."""

    category: str
    reason: str


def categorize(error: object, message: str | None = None) -> CategorizedError:
    """Assign ``error`` to a taxonomy category.

    Args:
        error: An :class:`Exception` instance, an exception class, or a string
            naming the type. For an instance, ``message`` defaults to its
            ``str()``.
        message: Optional message to scan; overrides an instance's own message.

    Returns:
        A :class:`CategorizedError` whose ``category`` is one of
        :data:`CATEGORIES`. Rules are evaluated in a fixed priority order
        (rate-limit, auth, network, validation) against the combined
        type-name-and-message text; the first matching rule wins.

    Raises:
        TypeError: ``error`` is not a supported type, or ``message`` is not a
            string or ``None``.
    """
    if message is not None and not isinstance(message, str):
        raise TypeError("message must be a string or None")

    if isinstance(error, BaseException):
        type_name = type(error).__name__
        text = message if message is not None else str(error)
    elif isinstance(error, type) and issubclass(error, BaseException):
        type_name = error.__name__
        text = message or ""
    elif isinstance(error, str):
        type_name = error
        text = message or ""
    else:
        raise TypeError("error must be an exception, exception class, or string")

    haystack = f"{type_name}\n{text}".lower()
    for category, hints in _RULES:
        for hint in hints:
            if hint in haystack:
                return CategorizedError(category, f"matched {hint!r}")
    return CategorizedError(UNKNOWN, "no category signal matched")


def category_of(error: object, message: str | None = None) -> str:
    """Return just the category string for ``error``."""
    return categorize(error, message).category
