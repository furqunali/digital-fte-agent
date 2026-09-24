"""Compute processing throughput from a count and an elapsed interval.

After a batch finishes, the loop wants to know how fast it went: items per
second, per minute, and how long the average item took. :func:`throughput` takes
the number of items processed and the already-measured ``elapsed`` interval and
returns an immutable :class:`Throughput` record. It reads no clock -- the caller
supplies the elapsed time -- so the same inputs always produce the same figures.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _require_count(name: str, value: object) -> int:
    """Return ``value`` as a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _require_elapsed(name: str, value: object) -> float:
    """Return ``value`` as a finite float that is strictly positive."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if number <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return number


@dataclass(frozen=True)
class Throughput:
    """A throughput measurement over a fixed interval.

    Args:
        items: The number of items processed (``>= 0``).
        elapsed: The interval over which they were processed, in seconds.
        per_second: ``items / elapsed``.
    """

    items: int
    elapsed: float
    per_second: float

    @property
    def per_minute(self) -> float:
        """Throughput expressed as items per minute."""
        return self.per_second * 60.0

    @property
    def seconds_per_item(self) -> float:
        """Average seconds per item; ``0.0`` when no items were processed."""
        if self.items == 0:
            return 0.0
        return self.elapsed / self.items


def throughput(items: int, elapsed: float) -> Throughput:
    """Return the :class:`Throughput` for ``items`` processed over ``elapsed``.

    Args:
        items: Items processed (``>= 0``).
        elapsed: Elapsed interval in seconds (``> 0``, finite).
    """
    items = _require_count("items", items)
    elapsed = _require_elapsed("elapsed", elapsed)
    return Throughput(items=items, elapsed=elapsed, per_second=items / elapsed)
