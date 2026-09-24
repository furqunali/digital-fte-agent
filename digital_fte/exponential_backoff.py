"""Capped exponential backoff schedules for the Digital FTE action stage.

When the reasoning loop retries a flaky side effect it should wait longer after
each successive failure so it neither gives up too soon nor hammers a struggling
resource. This module computes that wait *purely*: the delay before an attempt is
a deterministic function of the attempt number and the schedule parameters, with
no wall-clock reads and no randomness. Jitter, if wanted, is applied separately
by :mod:`digital_fte.jitter` so this schedule stays exactly reproducible.

Timing model
------------
Attempts are numbered from ``1``. The delay *before* attempt ``n`` is::

    min(base * factor ** (n - 1), max_delay)

so with ``base=1`` and ``factor=2`` the waits before attempts 1, 2, 3, 4 are
``1, 2, 4, 8`` seconds, each optionally clamped by ``max_delay``. A ``base`` of
``0`` yields an all-zero schedule (retry immediately every time).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _require_real(name: str, value: object, *, minimum: float) -> float:
    """Return ``value`` as a finite float that is at least ``minimum``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):  # NaN is unordered; guard before comparisons.
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


def _require_attempts(name: str, value: object) -> int:
    """Return ``value`` as an int that is at least ``1``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


def backoff_delay(
    attempt: int,
    *,
    base: float,
    factor: float = 2.0,
    max_delay: float | None = None,
) -> float:
    """Return the deterministic wait, in seconds, before ``attempt``.

    Args:
        attempt: The 1-indexed attempt number (``>= 1``).
        base: The wait before the first attempt in seconds (``>= 0``).
        factor: The growth multiplier applied per attempt (``>= 1``).
        max_delay: An optional per-attempt ceiling in seconds (``> 0`` or
            ``None`` for no ceiling).

    The result is ``min(base * factor ** (attempt - 1), max_delay)``.
    """
    attempt = _require_attempts("attempt", attempt)
    base = _require_real("base", base, minimum=0.0)
    factor = _require_real("factor", factor, minimum=1.0)
    raw = base * (factor ** (attempt - 1))
    if max_delay is not None:
        ceiling = _require_real("max_delay", max_delay, minimum=0.0)
        if ceiling <= 0.0:
            raise ValueError("max_delay must be > 0 when provided")
        return min(raw, ceiling)
    return raw


def backoff_schedule(
    attempts: int,
    *,
    base: float,
    factor: float = 2.0,
    max_delay: float | None = None,
) -> tuple[float, ...]:
    """Return the full delay sequence for ``attempts`` attempts.

    The returned tuple has length ``attempts``; index ``i`` is the wait before
    attempt ``i + 1`` as computed by :func:`backoff_delay`.
    """
    attempts = _require_attempts("attempts", attempts)
    return tuple(
        backoff_delay(n, base=base, factor=factor, max_delay=max_delay)
        for n in range(1, attempts + 1)
    )


@dataclass(frozen=True)
class BackoffSchedule:
    """An immutable, reusable capped exponential backoff schedule.

    Args:
        base: Wait before the first attempt in seconds (``>= 0``).
        factor: Growth multiplier applied per attempt (``>= 1``).
        max_delay: Optional per-attempt ceiling in seconds (``> 0`` or ``None``).

    All fields are validated on construction; :meth:`delay_before`,
    :meth:`schedule`, and :meth:`total_delay` are pure functions of them.
    """

    base: float = 0.5
    factor: float = 2.0
    max_delay: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "base", _require_real("base", self.base, minimum=0.0))
        object.__setattr__(self, "factor", _require_real("factor", self.factor, minimum=1.0))
        if self.max_delay is not None:
            ceiling = _require_real("max_delay", self.max_delay, minimum=0.0)
            if ceiling <= 0.0:
                raise ValueError("max_delay must be > 0 when provided")
            object.__setattr__(self, "max_delay", ceiling)

    def delay_before(self, attempt: int) -> float:
        """Return the wait before ``attempt`` (see :func:`backoff_delay`)."""
        return backoff_delay(
            attempt, base=self.base, factor=self.factor, max_delay=self.max_delay
        )

    def schedule(self, attempts: int) -> tuple[float, ...]:
        """Return the delay sequence for ``attempts`` attempts."""
        return backoff_schedule(
            attempts, base=self.base, factor=self.factor, max_delay=self.max_delay
        )

    def total_delay(self, attempts: int) -> float:
        """Return the sum of all waits across ``attempts`` attempts."""
        return math.fsum(self.schedule(attempts))
