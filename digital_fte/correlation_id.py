"""Deterministic correlation ids for tracing Digital FTE work.

Every unit of work in a run wants a *correlation id*: a short opaque token that
threads through logs, spans, and downstream calls so one request can be
reconstructed after the fact. Randomly generated ids make runs impossible to
replay; this module instead derives ids deterministically from a *seed* string
and an integer *counter*, so the same (seed, counter) pair always yields the
same id and a replayed run produces an identical trace.

Ids are the leading hex of a SHA-256 over a length-prefixed seed and the
counter. Length-prefixing the seed means ``("ab", 1)`` and ``("a", 1)`` (or a
seed that happens to contain digits) can never collide with a different split.
No clock, no randomness.
"""
from __future__ import annotations

import hashlib

_MIN_LENGTH = 4
_MAX_LENGTH = 64  # a full SHA-256 hex digest


def _validate_counter(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("counter must be an integer")
    if value < 0:
        raise ValueError("counter must be >= 0")
    return value


def _validate_length(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("length must be an integer")
    if value < _MIN_LENGTH or value > _MAX_LENGTH:
        raise ValueError(f"length must be within {_MIN_LENGTH}..{_MAX_LENGTH}")
    return value


def correlation_id(seed: str, counter: int, *, length: int = 16) -> str:
    """Return a deterministic hex correlation id for ``(seed, counter)``.

    Args:
        seed: A stable string identifying the run/context (e.g. a run id).
        counter: A non-negative integer distinguishing ids within the seed;
            increment it per unit of work.
        length: Number of leading hex characters to return, ``4..64``
            (default ``16``, i.e. 64 bits).

    Returns:
        A lowercase hex string of exactly ``length`` characters. Distinct
        ``(seed, counter)`` inputs give distinct ids barring hash collision.

    Raises:
        TypeError: ``seed`` is not a string, or ``counter``/``length`` are not
            integers (bools are rejected).
        ValueError: ``counter`` is negative, or ``length`` is out of range.
    """
    if not isinstance(seed, str):
        raise TypeError("seed must be a string")
    counter = _validate_counter(counter)
    length = _validate_length(length)

    hasher = hashlib.sha256()
    seed_bytes = seed.encode("utf-8")
    # Length-prefix the seed so seed/counter boundaries are unambiguous.
    hasher.update(f"{len(seed_bytes)}:".encode("ascii"))
    hasher.update(seed_bytes)
    hasher.update(f":{counter}".encode("ascii"))
    return hasher.hexdigest()[:length]


def sequence(seed: str, count: int, *, start: int = 0, length: int = 16) -> tuple[str, ...]:
    """Return ``count`` correlation ids for consecutive counters from ``start``.

    A convenience for pre-allocating a deterministic batch of ids. Raises
    ``ValueError`` if ``count`` is negative.
    """
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError("count must be an integer")
    if count < 0:
        raise ValueError("count must be >= 0")
    start = _validate_counter(start)
    return tuple(
        correlation_id(seed, start + i, length=length) for i in range(count)
    )
