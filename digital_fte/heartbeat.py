"""Decide whether a heartbeat is healthy or stale.

A supervised Digital FTE emits a heartbeat as it works; a watchdog decides it is
unhealthy if too long passes without one. :func:`check_heartbeat` compares the
last-seen time against ``now`` and a ``max_staleness`` allowance, returning an
immutable :class:`HeartbeatStatus`. Both ``now`` and ``last_seen`` are supplied
by the caller -- the module never reads a clock -- so the verdict is fully
reproducible in tests.

A heartbeat is ``healthy`` while its staleness (``now - last_seen``) is at most
``max_staleness`` and ``stale`` once it exceeds it. A ``last_seen`` in the future
relative to ``now`` (clock skew) yields a negative staleness and is treated as
healthy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

HEALTHY = "healthy"
STALE = "stale"


def _require_real(name: str, value: object) -> float:
    """Return ``value`` as a finite float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    return number


def _require_positive(name: str, value: object) -> float:
    """Return ``value`` as a finite, strictly positive float."""
    number = _require_real(name, value)
    if number <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return number


@dataclass(frozen=True)
class HeartbeatStatus:
    """The health verdict for a heartbeat.

    Args:
        state: Either :data:`HEALTHY` or :data:`STALE`.
        staleness: ``now - last_seen`` in seconds (negative under clock skew).
        max_staleness: The allowance the staleness was compared against.
    """

    state: str
    staleness: float
    max_staleness: float

    @property
    def healthy(self) -> bool:
        """Whether the heartbeat is within its staleness allowance."""
        return self.state == HEALTHY

    @property
    def stale(self) -> bool:
        """Whether the heartbeat has exceeded its staleness allowance."""
        return self.state == STALE


def check_heartbeat(
    last_seen: float, now: float, max_staleness: float
) -> HeartbeatStatus:
    """Classify a heartbeat as healthy or stale.

    Args:
        last_seen: When the last heartbeat arrived (finite).
        now: The current time (finite).
        max_staleness: The maximum tolerated staleness in seconds (``> 0``).

    Returns a :data:`STALE` status when ``now - last_seen > max_staleness`` and a
    :data:`HEALTHY` status otherwise.
    """
    last_seen = _require_real("last_seen", last_seen)
    now = _require_real("now", now)
    max_staleness = _require_positive("max_staleness", max_staleness)
    staleness = now - last_seen
    state = STALE if staleness > max_staleness else HEALTHY
    return HeartbeatStatus(
        state=state, staleness=staleness, max_staleness=max_staleness
    )
