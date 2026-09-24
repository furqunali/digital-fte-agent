"""Time-to-live dedupe cache with caller-supplied time.

The intake and action stages of a reasoning loop need to remember "have I
handled this recently?" without leaking memory forever. A TTL cache answers
that: an entry inserted at time ``t`` is considered present until ``t + ttl``
and is treated as absent thereafter.

Time is never read from a clock inside this module -- the caller passes ``now``
on every ``put``/``get``/``contains`` call, exactly as the rest of the package
injects time. That keeps expiry fully deterministic and replayable in tests.
Expired entries are treated as absent immediately; they are also physically
dropped lazily on access and can be swept in bulk with :meth:`purge`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _validate_ttl(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("ttl must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError("ttl must not be NaN")
    if math.isinf(number):
        raise ValueError("ttl must be finite")
    if number <= 0.0:
        raise ValueError("ttl must be > 0")
    return number


def _validate_now(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("now must be a real number")
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise ValueError("now must be finite")
    return number


@dataclass(frozen=True)
class _Entry:
    value: object
    expires_at: float


class TtlCache:
    """A key/value cache whose entries expire ``ttl`` seconds after insertion.

    Args:
        ttl: Lifetime of an entry in seconds; must be a positive, finite number.

    All time-aware methods take ``now`` (a real, finite number) from the caller.
    An entry is present while ``now < expires_at`` and absent once
    ``now >= expires_at``.
    """

    def __init__(self, ttl: float) -> None:
        self.ttl = _validate_ttl(ttl)
        self._entries: dict[object, _Entry] = {}

    def __len__(self) -> int:
        """Number of stored entries, *including* any not yet purged expired ones."""
        return len(self._entries)

    def put(self, key: object, now: float, value: object = None) -> None:
        """Insert or overwrite ``key`` with an expiry of ``now + ttl``."""
        now = _validate_now(now)
        self._entries[key] = _Entry(value=value, expires_at=now + self.ttl)

    def contains(self, key: object, now: float) -> bool:
        """Return whether ``key`` is present and unexpired at ``now``.

        A lookup that finds an expired entry drops it as a side effect so the
        cache does not accumulate dead keys under repeated access.
        """
        now = _validate_now(now)
        entry = self._entries.get(key)
        if entry is None:
            return False
        if now >= entry.expires_at:
            del self._entries[key]
            return False
        return True

    def get(self, key: object, now: float, default: object = None) -> object:
        """Return the value for ``key`` if present and unexpired, else ``default``."""
        if self.contains(key, now):
            return self._entries[key].value
        return default

    def add(self, key: object, now: float, value: object = None) -> bool:
        """Insert ``key`` only if not already live; return ``True`` if inserted.

        This is the dedupe primitive: the first time a key is seen (or the first
        time after it expired) it is stored and ``True`` is returned; while a
        live entry exists a duplicate ``add`` leaves it untouched and returns
        ``False``.
        """
        if self.contains(key, now):
            return False
        self.put(key, now, value)
        return True

    def expires_at(self, key: object) -> float | None:
        """Return the raw expiry time for ``key``, or ``None`` if unknown."""
        entry = self._entries.get(key)
        return None if entry is None else entry.expires_at

    def purge(self, now: float) -> int:
        """Drop every entry that has expired by ``now``; return how many were removed."""
        now = _validate_now(now)
        expired = [k for k, e in self._entries.items() if now >= e.expires_at]
        for key in expired:
            del self._entries[key]
        return len(expired)

    def active_keys(self, now: float) -> tuple[object, ...]:
        """Return the keys still live at ``now`` (insertion order preserved)."""
        now = _validate_now(now)
        return tuple(k for k, e in self._entries.items() if now < e.expires_at)

    def clear(self) -> None:
        """Remove all entries regardless of expiry."""
        self._entries.clear()
