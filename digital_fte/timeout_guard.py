"""Classify an operation's elapsed time against a budget.

After the loop times an operation it needs a crisp verdict: did the work finish
inside its budget, or did it overrun? :func:`classify_timeout` turns a measured
``elapsed`` and a ``budget`` into an immutable :class:`TimeoutStatus` carrying
that verdict plus the remaining headroom (or the overrun). The function is pure
-- it measures nothing itself; the caller supplies the already-measured elapsed
time -- so results are fully reproducible.

An operation is considered ``timed_out`` once ``elapsed`` reaches the budget,
i.e. ``elapsed >= budget``; reaching the budget exactly means the time is gone.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

OK = "ok"
TIMED_OUT = "timed_out"


def _require_real(name: str, value: object, *, minimum: float) -> float:
    """Return ``value`` as a finite float that is at least ``minimum``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


@dataclass(frozen=True)
class TimeoutStatus:
    """The verdict of a timeout classification.

    Args:
        state: Either :data:`OK` or :data:`TIMED_OUT`.
        elapsed: The measured elapsed time in seconds.
        budget: The allowed budget in seconds.
        remaining: Seconds of headroom left, ``0.0`` once timed out.
        overrun: Seconds past the budget, ``0.0`` while still within it.
    """

    state: str
    elapsed: float
    budget: float
    remaining: float
    overrun: float

    @property
    def timed_out(self) -> bool:
        """Whether the operation exceeded (or exactly hit) its budget."""
        return self.state == TIMED_OUT

    @property
    def ok(self) -> bool:
        """Whether the operation finished within its budget."""
        return self.state == OK


def classify_timeout(elapsed: float, budget: float) -> TimeoutStatus:
    """Classify ``elapsed`` against ``budget`` into a :class:`TimeoutStatus`.

    Args:
        elapsed: Measured elapsed seconds (``>= 0``, finite).
        budget: Allowed budget in seconds (``> 0``, finite).

    Returns a :data:`TIMED_OUT` status when ``elapsed >= budget`` and an
    :data:`OK` status otherwise. ``remaining`` and ``overrun`` are each clamped
    to be non-negative and never both positive.
    """
    elapsed = _require_real("elapsed", elapsed, minimum=0.0)
    budget = _require_real("budget", budget, minimum=0.0)
    if budget <= 0.0:
        raise ValueError("budget must be > 0")

    if elapsed >= budget:
        return TimeoutStatus(
            state=TIMED_OUT,
            elapsed=elapsed,
            budget=budget,
            remaining=0.0,
            overrun=elapsed - budget,
        )
    return TimeoutStatus(
        state=OK,
        elapsed=elapsed,
        budget=budget,
        remaining=budget - elapsed,
        overrun=0.0,
    )
