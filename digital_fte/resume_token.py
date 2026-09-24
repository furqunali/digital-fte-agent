"""Opaque, URL-safe resume tokens for Digital FTE runs.

When a run pauses it hands the caller a single string that captures where to
pick up: a numeric ``offset`` plus an opaque ``state`` dict of engine-specific
bookkeeping. :func:`encode_token` serialises that pair to a compact,
URL-safe base64 string suitable for a query parameter or a header;
:func:`decode_token` reverses it and validates the structure.

Encoding is deterministic -- the JSON payload is emitted with sorted keys and
no incidental whitespace -- so the same ``(offset, state)`` always yields the
same token. A payload is versioned so future formats can be told apart, and any
malformed input raises :class:`InvalidResumeToken` rather than returning junk.
"""
from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

#: Payload format version embedded in every token.
VERSION = 1


class InvalidResumeToken(Exception):
    """Raised when a token cannot be decoded or fails structural checks."""


@dataclass(frozen=True)
class ResumeToken:
    """A decoded resume position.

    Attributes:
        offset: The non-negative item offset to resume from.
        state: Opaque engine state; an empty dict when none was supplied.
    """

    offset: int
    state: dict[str, Any]


def _validate_offset(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("offset must be an integer")
    if value < 0:
        raise ValueError("offset must be >= 0")
    return value


def _validate_state(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError("state must be a dict or None")
    for key in value:
        if not isinstance(key, str):
            raise TypeError("state keys must be strings")
    return value


def encode_token(offset: int, state: dict[str, Any] | None = None) -> str:
    """Encode ``offset`` and ``state`` into a URL-safe base64 token.

    Args:
        offset: Non-negative resume offset.
        state: Optional JSON-serialisable dict of opaque engine state.

    Returns:
        A URL-safe base64 ASCII string.

    Raises:
        TypeError: If ``offset`` is not an int or ``state`` is not a dict/None.
        ValueError: If ``offset`` is negative or ``state`` is not
            JSON-serialisable.
    """
    offset = _validate_offset(offset)
    state = _validate_state(state)
    payload = {"v": VERSION, "offset": offset, "state": state}
    try:
        raw = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"state is not JSON-serialisable: {exc}") from exc
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_token(token: str) -> ResumeToken:
    """Decode a token produced by :func:`encode_token`.

    Args:
        token: The URL-safe base64 string to decode.

    Returns:
        The decoded :class:`ResumeToken`.

    Raises:
        InvalidResumeToken: If the string is not a valid token -- bad base64,
            invalid JSON, an unknown version, or a malformed structure.
    """
    if not isinstance(token, str) or not token:
        raise InvalidResumeToken("token must be a non-empty string")

    # Restore any base64 padding the transport may have stripped.
    padded = token + "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
        raise InvalidResumeToken(f"not valid base64: {exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidResumeToken(f"not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise InvalidResumeToken("payload must be a JSON object")
    if payload.get("v") != VERSION:
        raise InvalidResumeToken(f"unsupported token version {payload.get('v')!r}")

    offset = payload.get("offset")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise InvalidResumeToken("payload offset must be a non-negative integer")

    state = payload.get("state", {})
    if not isinstance(state, dict):
        raise InvalidResumeToken("payload state must be an object")

    return ResumeToken(offset=offset, state=state)
