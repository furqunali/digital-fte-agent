"""Classify errors as transient or permanent for retry decisions.

When an action fails, the loop must decide whether retrying could plausibly
succeed. A *transient* failure (a timeout, a dropped connection, a throttle) is
worth retrying; a *permanent* one (bad input, missing permission, a 404) is not
-- retrying only wastes budget. This module makes that call deterministically
from the error's *type name* and *message*, with no clock and no randomness.

Classification is a pure function of two strings. It first looks for strong
signals in the exception's class name, then in keywords found in the message.
When nothing matches, the disposition is :data:`UNKNOWN`, which callers should
treat conservatively (typically: do not retry).
"""
from __future__ import annotations

from dataclasses import dataclass

TRANSIENT = "transient"
PERMANENT = "permanent"
UNKNOWN = "unknown"

# Substrings (matched case-insensitively) in an exception's class name.
_TRANSIENT_TYPE_HINTS = (
    "timeout",
    "timederror",
    "connection",
    "connectionreset",
    "connectionaborted",
    "temporary",
    "unavailable",
    "throttl",
    "ratelimit",
    "toomanyrequests",
    "brokenpipe",
    "again",  # e.g. socket "try again"
)
_PERMANENT_TYPE_HINTS = (
    "value",
    "type",
    "key",
    "attribute",
    "index",
    "notfound",
    "notimplemented",
    "permission",
    "auth",
    "forbidden",
    "unauthorized",
    "validation",
    "assertion",
    "lookup",
)

# Keywords (matched case-insensitively) inside the error message.
_TRANSIENT_MESSAGE_HINTS = (
    "timed out",
    "timeout",
    "temporarily",
    "temporary",
    "connection reset",
    "connection refused",
    "connection aborted",
    "try again",
    "unavailable",
    "throttled",
    "rate limit",
    "too many requests",
    "503",
    "502",
    "504",
    "429",
)
_PERMANENT_MESSAGE_HINTS = (
    "not found",
    "forbidden",
    "unauthorized",
    "permission denied",
    "invalid",
    "malformed",
    "does not exist",
    "already exists",
    "400",
    "401",
    "403",
    "404",
    "409",
    "422",
)


@dataclass(frozen=True)
class Classification:
    """The outcome of classifying an error.

    Args:
        disposition: One of :data:`TRANSIENT`, :data:`PERMANENT`, :data:`UNKNOWN`.
        reason: A short human-readable explanation of which signal decided it.
    """

    disposition: str
    reason: str

    @property
    def is_transient(self) -> bool:
        return self.disposition == TRANSIENT

    @property
    def is_permanent(self) -> bool:
        return self.disposition == PERMANENT


def _first_hint(haystack: str, hints: tuple[str, ...]) -> str | None:
    for hint in hints:
        if hint in haystack:
            return hint
    return None


def classify(error: object, message: str | None = None) -> Classification:
    """Classify ``error`` as transient, permanent, or unknown.

    Args:
        error: An :class:`Exception` instance, an exception *class*, or a string
            naming the exception type. When an instance is given and ``message``
            is omitted, the instance's ``str()`` is used as the message.
        message: Optional error message to scan for keywords. Overrides the
            message taken from an exception instance.

    Returns:
        A :class:`Classification`. Type-name signals take precedence over
        message signals; a transient type hint wins over a permanent message
        hint and vice-versa is resolved in favour of the type hint.

    Raises:
        TypeError: ``error`` is not an exception, exception class, or string, or
            ``message`` is neither a string nor ``None``.
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

    name_key = type_name.lower()
    text_key = text.lower()

    # 1. Strong signal: the exception's own type name.
    hit = _first_hint(name_key, _TRANSIENT_TYPE_HINTS)
    if hit is not None:
        return Classification(TRANSIENT, f"type name contains {hit!r}")
    hit = _first_hint(name_key, _PERMANENT_TYPE_HINTS)
    if hit is not None:
        return Classification(PERMANENT, f"type name contains {hit!r}")

    # 2. Weaker signal: keywords in the message.
    hit = _first_hint(text_key, _TRANSIENT_MESSAGE_HINTS)
    if hit is not None:
        return Classification(TRANSIENT, f"message mentions {hit!r}")
    hit = _first_hint(text_key, _PERMANENT_MESSAGE_HINTS)
    if hit is not None:
        return Classification(PERMANENT, f"message mentions {hit!r}")

    return Classification(UNKNOWN, "no known transient or permanent signal")


def is_transient(error: object, message: str | None = None) -> bool:
    """Convenience wrapper returning ``True`` only for a transient classification."""
    return classify(error, message).is_transient
