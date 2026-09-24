"""Time-bounded ownership leases with caller-supplied time.

When a Digital FTE run claims an exclusive resource -- a task, a folder, a lock
-- it takes a *lease*: ownership that is valid only until an expiry time. If the
owner crashes, the lease simply expires and another worker may claim it, so no
resource is held forever. Leases are the cooperative alternative to a hard
lock.

A :class:`Lease` is an immutable record of ``owner`` and ``expires_at``. Every
question about it takes ``now`` from the caller -- ``is_held(now)``,
``is_expired(now)`` -- and renewal returns a *new* lease rather than mutating in
place. There is no clock inside this module, so lease logic is deterministic and
replayable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace


def _validate_time(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    return number


def _validate_ttl(value: object) -> float:
    ttl = _validate_time("ttl", value)
    if ttl <= 0.0:
        raise ValueError("ttl must be > 0")
    return ttl


@dataclass(frozen=True)
class Lease:
    """An immutable ownership lease valid until ``expires_at``.

    Args:
        owner: Non-empty identifier of the holder.
        expires_at: Absolute time, in seconds, at/after which the lease is
            expired.

    Prefer :meth:`acquire` to construct a lease from a ``now`` and ``ttl``; the
    constructor is available when the expiry is already known.
    """

    owner: str
    expires_at: float

    def __post_init__(self) -> None:
        if not isinstance(self.owner, str):
            raise TypeError("owner must be a string")
        if not self.owner.strip():
            raise ValueError("owner must be a non-empty string")
        object.__setattr__(self, "expires_at", _validate_time("expires_at", self.expires_at))

    @classmethod
    def acquire(cls, owner: str, now: float, ttl: float) -> "Lease":
        """Create a lease held by ``owner`` from ``now`` for ``ttl`` seconds."""
        now = _validate_time("now", now)
        ttl = _validate_ttl(ttl)
        return cls(owner=owner, expires_at=now + ttl)

    def is_expired(self, now: float) -> bool:
        """Return whether the lease has expired at ``now`` (``now >= expires_at``)."""
        now = _validate_time("now", now)
        return now >= self.expires_at

    def is_held(self, now: float) -> bool:
        """Return whether the lease is still valid at ``now`` (``now < expires_at``)."""
        return not self.is_expired(now)

    def remaining(self, now: float) -> float:
        """Return seconds left before expiry at ``now``; ``0.0`` once expired."""
        now = _validate_time("now", now)
        return max(0.0, self.expires_at - now)

    def renew(self, now: float, ttl: float) -> "Lease":
        """Return a new lease for the same owner expiring ``ttl`` after ``now``.

        Renewal extends (or resets) the expiry regardless of whether the lease
        had already expired -- the caller decides, by choosing when to renew,
        whether a lapsed lease may be reclaimed.
        """
        now = _validate_time("now", now)
        ttl = _validate_ttl(ttl)
        return replace(self, expires_at=now + ttl)

    def transfer(self, new_owner: str, now: float, ttl: float) -> "Lease":
        """Return a fresh lease held by ``new_owner`` from ``now`` for ``ttl``."""
        return Lease.acquire(new_owner, now, ttl)
