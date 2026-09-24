"""Deadlines for time-boxing Digital FTE work.

A reasoning loop often runs under a budget: "spend at most 30 seconds on this
task". A :class:`Deadline` captures the fixed facts of that budget -- the start
time and how long is allowed -- as an immutable record. Because the module never
reads a clock itself, every query takes the current time ``now`` as an explicit
parameter, so the same deadline produces identical answers when replayed in a
test with a fake clock.

Times are plain floats on a caller-chosen monotonic scale (for example
``time.monotonic()``); only differences matter, so the origin is irrelevant.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _require_real(name: str, value: object, *, minimum: float | None = None) -> float:
    """Return ``value`` as a finite float, optionally bounded below."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


@dataclass(frozen=True)
class Deadline:
    """An immutable time budget starting at ``start`` and lasting ``budget``.

    Args:
        start: The monotonic time the budget began (finite).
        budget: The allowed duration in seconds (``> 0``, finite).

    The absolute expiry instant is :attr:`deadline` (``start + budget``). All
    query methods take the current time ``now`` explicitly and never read a
    clock, keeping behaviour reproducible.
    """

    start: float
    budget: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "start", _require_real("start", self.start))
        budget = _require_real("budget", self.budget, minimum=0.0)
        if budget <= 0.0:
            raise ValueError("budget must be > 0")
        object.__setattr__(self, "budget", budget)

    @property
    def deadline(self) -> float:
        """The absolute instant the budget expires (``start + budget``)."""
        return self.start + self.budget

    def remaining(self, now: float) -> float:
        """Return seconds left at ``now``, clamped to ``0.0`` once expired."""
        now = _require_real("now", now)
        left = self.deadline - now
        return left if left > 0.0 else 0.0

    def overrun(self, now: float) -> float:
        """Return how far ``now`` is past the deadline, ``0.0`` if not expired."""
        now = _require_real("now", now)
        over = now - self.deadline
        return over if over > 0.0 else 0.0

    def expired(self, now: float) -> bool:
        """Return ``True`` when ``now`` has reached or passed the deadline."""
        now = _require_real("now", now)
        return now >= self.deadline

    def elapsed(self, now: float) -> float:
        """Return seconds elapsed since ``start``, clamped to ``0.0`` before it."""
        now = _require_real("now", now)
        gone = now - self.start
        return gone if gone > 0.0 else 0.0

    def fraction_elapsed(self, now: float) -> float:
        """Return the fraction of the budget consumed at ``now``, in ``[0, 1]``."""
        return min(1.0, self.elapsed(now) / self.budget)
