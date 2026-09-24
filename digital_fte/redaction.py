"""Redact secrets and PII from log strings before they are persisted.

The telemetry and audit stages of a Digital FTE run emit a lot of text, and
that text often carries things that must never land in a log: API keys, bearer
tokens, and email addresses. This module masks those patterns in a string
deterministically -- the same input always yields the same redacted output, so
redaction can run safely inside the logging path with no clock and no
randomness.

Each pattern is replaced with a fixed placeholder that names *what* was hidden
(``[REDACTED_EMAIL]`` etc.) so the log stays readable and greppable while the
sensitive value is gone. Redaction is conservative in one direction only: it
never invents new characters that could be mistaken for real data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_PLACEHOLDER = "[REDACTED_EMAIL]"
BEARER_PLACEHOLDER = "Bearer [REDACTED_TOKEN]"
API_KEY_PLACEHOLDER = "[REDACTED_API_KEY]"
GENERIC_PLACEHOLDER = "[REDACTED_SECRET]"

# Order matters: more specific patterns run first so a bearer token is not also
# caught by the generic long-token rule.
_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "email",
        re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
        EMAIL_PLACEHOLDER,
    ),
    (
        "bearer",
        re.compile(r"[Bb]earer\s+[A-Za-z0-9._\-]+"),
        BEARER_PLACEHOLDER,
    ),
    (
        "provider_key",
        # Common provider style keys, e.g. "sk-...", "sk_live_...", "AKIA...".
        re.compile(r"\b(?:sk|pk|rk)[-_][A-Za-z0-9]{8,}\b|\bAKIA[0-9A-Z]{12,}\b"),
        API_KEY_PLACEHOLDER,
    ),
    (
        "assigned_secret",
        # "api_key=...", "apikey: ...", "token=...", "password=...", "secret=..."
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|token|secret|password|passwd|pwd|access[_-]?key)\b"
            r"\s*[:=]\s*(\"[^\"]+\"|'[^']+'|\S+)"
        ),
        None,  # handled specially to keep the label
    ),
)


@dataclass(frozen=True)
class RedactionResult:
    """The redacted text plus a count of substitutions made, per category."""

    text: str
    counts: dict


def _redact_assigned(match: re.Match[str]) -> str:
    label = match.group(1)
    return f"{label}={GENERIC_PLACEHOLDER}"


def redact(text: str) -> str:
    """Return ``text`` with emails, bearer tokens, and API keys masked.

    Args:
        text: The log string to sanitise.

    Returns:
        A new string with every recognised secret/PII pattern replaced by a
        descriptive placeholder. Text with nothing sensitive is returned
        unchanged (aside from being a new equal string).

    Raises:
        TypeError: ``text`` is not a string.
    """
    return redact_verbose(text).text


def redact_verbose(text: str) -> RedactionResult:
    """Like :func:`redact` but also report how many of each pattern were masked.

    The returned :class:`RedactionResult` carries a ``counts`` mapping keyed by
    pattern name (``"email"``, ``"bearer"``, ``"provider_key"``,
    ``"assigned_secret"``) with the number of substitutions each made.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    counts: dict[str, int] = {}
    result = text
    for name, pattern, replacement in _PATTERNS:
        if name == "assigned_secret":
            result, n = pattern.subn(_redact_assigned, result)
        else:
            result, n = pattern.subn(replacement, result)
        if n:
            counts[name] = n
    return RedactionResult(text=result, counts=counts)


def contains_secret(text: str) -> bool:
    """Return whether ``text`` appears to contain any redactable secret/PII."""
    return bool(redact_verbose(text).counts)
