"""Compute an event rate over a trailing sliding window.

To answer "how many actions per second am I firing right now?" the loop keeps a
list of event timestamps and asks how many fall inside the trailing ``window``
ending at ``now``. Both ``now`` and the ``window`` are passed in explicitly and
the timestamps come from the caller, so nothing here reads a clock and the same
inputs always yield the same rate.

An event at time ``t`` counts when ``now - window <= t <= now``; events in the
future (``t > now``) and events older than the window are ignored.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
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


def _coerce_timestamps(timestamps: Iterable[float]) -> tuple[float, ...]:
    """Validate and materialise ``timestamps`` into a tuple of finite floats."""
    if isinstance(timestamps, (str, bytes)):
        raise TypeError("timestamps must be an iterable of numbers, not a string")
    try:
        items = list(timestamps)
    except TypeError as exc:
        raise TypeError("timestamps must be iterable") from exc
    return tuple(_require_real("timestamp", t) for t in items)


@dataclass(frozen=True)
class WindowRate:
    """The event rate measured over a trailing window.

    Args:
        count: Events falling inside the window.
        window: The window width in seconds.
        per_second: ``count / window``.
    """

    count: int
    window: float
    per_second: float

    @property
    def per_minute(self) -> float:
        """The rate expressed as events per minute."""
        return self.per_second * 60.0


def count_in_window(
    timestamps: Iterable[float], *, now: float, window: float
) -> int:
    """Return how many ``timestamps`` fall within the trailing ``window``.

    An event ``t`` is counted when ``now - window <= t <= now``.
    """
    now = _require_real("now", now)
    window = _require_real("window", window, minimum=0.0)
    if window <= 0.0:
        raise ValueError("window must be > 0")
    lower = now - window
    stamps = _coerce_timestamps(timestamps)
    return sum(1 for t in stamps if lower <= t <= now)


def rate_in_window(
    timestamps: Iterable[float], *, now: float, window: float
) -> WindowRate:
    """Return the :class:`WindowRate` for ``timestamps`` over the ``window``.

    The per-second rate is the in-window count divided by the window width.
    """
    now = _require_real("now", now)
    window = _require_real("window", window, minimum=0.0)
    if window <= 0.0:
        raise ValueError("window must be > 0")
    lower = now - window
    stamps = _coerce_timestamps(timestamps)
    count = sum(1 for t in stamps if lower <= t <= now)
    return WindowRate(count=count, window=window, per_second=count / window)
