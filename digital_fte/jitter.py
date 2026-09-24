"""Deterministic jitter for backoff delays.

Spreading retries with a little jitter stops many agents that failed together
from retrying in lockstep and re-colliding. The usual recipe draws a random
number, which would make a run impossible to replay. Here the caller supplies
the random *fraction* (a value in ``0..1``) explicitly -- from a seeded RNG they
control, a hash, or a fixed value in tests -- so the jitter maths stay pure and
this module never touches a global RNG.

Two classic strategies from the "Exponential Backoff and Jitter" literature are
provided:

* **full jitter** -- ``delay * fraction``; the wait is anywhere in ``[0, delay]``.
* **equal jitter** -- ``delay/2 + (delay/2) * fraction``; half the delay is kept
  as a floor and only the second half is randomised, giving ``[delay/2, delay]``.
"""
from __future__ import annotations

import math


def _require_non_negative(name: str, value: object) -> float:
    """Return ``value`` as a finite float that is ``>= 0``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if number < 0.0:
        raise ValueError(f"{name} must be >= 0")
    return number


def _require_fraction(name: str, value: object) -> float:
    """Return ``value`` as a float within the closed interval ``[0, 1]``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be within 0..1")
    return number


def full_jitter(delay: float, fraction: float) -> float:
    """Return ``delay`` scaled by ``fraction`` (full jitter).

    Args:
        delay: The base delay in seconds (``>= 0``).
        fraction: The caller-supplied random fraction in ``[0, 1]``.

    The result lies in ``[0, delay]``; ``fraction == 0`` gives ``0`` and
    ``fraction == 1`` gives the full ``delay``.
    """
    delay = _require_non_negative("delay", delay)
    fraction = _require_fraction("fraction", fraction)
    return delay * fraction


def equal_jitter(delay: float, fraction: float) -> float:
    """Return a half-fixed, half-random jitter of ``delay`` (equal jitter).

    Args:
        delay: The base delay in seconds (``>= 0``).
        fraction: The caller-supplied random fraction in ``[0, 1]``.

    The result is ``delay/2 + (delay/2) * fraction`` and lies in
    ``[delay/2, delay]``.
    """
    delay = _require_non_negative("delay", delay)
    fraction = _require_fraction("fraction", fraction)
    half = delay / 2.0
    return half + half * fraction


def clamped_jitter(
    delay: float,
    fraction: float,
    *,
    floor: float = 0.0,
    ceiling: float | None = None,
) -> float:
    """Return full jitter of ``delay`` clamped to ``[floor, ceiling]``.

    Useful when a jittered wait must respect a minimum backoff ``floor`` and/or
    a maximum ``ceiling``. ``floor`` must not exceed ``ceiling`` when both are
    given.
    """
    value = full_jitter(delay, fraction)
    floor = _require_non_negative("floor", floor)
    if ceiling is not None:
        ceiling = _require_non_negative("ceiling", ceiling)
        if floor > ceiling:
            raise ValueError("floor must not exceed ceiling")
        value = min(value, ceiling)
    return max(value, floor)
