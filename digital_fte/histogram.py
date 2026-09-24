"""Bucket a numeric sample into fixed-width bins.

A histogram is the cheapest way to see the *shape* of a distribution -- is
latency bimodal? are most costs tiny with a fat tail? :func:`histogram` divides
the range ``[low, high]`` into ``bins`` equal-width buckets and counts how many
sample values land in each. Values below ``low`` or above ``high`` are tallied
separately as underflow and overflow rather than being dropped, so no data is
silently lost.

The function is pure and deterministic: given the same sample and bounds it
always produces the same counts. Bins are half-open ``[edge, next_edge)`` except
the final bin, which is closed ``[edge, high]`` so that a value exactly equal to
``high`` lands in the last bucket rather than overflowing.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


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


def _require_bins(name: str, value: object) -> int:
    """Return ``value`` as an int that is at least ``1``."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


def _coerce_sample(sample: Iterable[float]) -> list[float]:
    """Validate ``sample`` into a list of finite floats (may be empty)."""
    if isinstance(sample, (str, bytes)):
        raise TypeError("sample must be an iterable of numbers, not a string")
    try:
        items = list(sample)
    except TypeError as exc:
        raise TypeError("sample must be iterable") from exc
    return [_require_real("sample value", value) for value in items]


@dataclass(frozen=True)
class Histogram:
    """The result of bucketing a sample into fixed-width bins.

    Args:
        low: Lower bound of the first bin.
        high: Upper bound of the last bin.
        width: The width of each bin (``(high - low) / bins``).
        edges: The ``bins + 1`` bin boundaries, ascending.
        counts: Per-bin counts, length ``bins``.
        underflow: Values strictly below ``low``.
        overflow: Values strictly above ``high``.
    """

    low: float
    high: float
    width: float
    edges: tuple[float, ...]
    counts: tuple[int, ...]
    underflow: int
    overflow: int

    @property
    def bins(self) -> int:
        """The number of bins."""
        return len(self.counts)

    @property
    def total(self) -> int:
        """Every value seen, including underflow and overflow."""
        return sum(self.counts) + self.underflow + self.overflow


def histogram(
    sample: Iterable[float], *, low: float, high: float, bins: int
) -> Histogram:
    """Bucket ``sample`` into ``bins`` equal-width bins spanning ``[low, high]``.

    Args:
        sample: An iterable of finite real numbers (may be empty).
        low: The lower edge of the first bin (finite).
        high: The upper edge of the last bin (finite, ``> low``).
        bins: The number of equal-width bins (``>= 1``).

    Values below ``low`` increment ``underflow``; values above ``high``
    increment ``overflow``. A value exactly equal to ``high`` falls in the last
    bin.
    """
    low = _require_real("low", low)
    high = _require_real("high", high)
    if high <= low:
        raise ValueError("high must be > low")
    bins = _require_bins("bins", bins)
    values = _coerce_sample(sample)

    width = (high - low) / bins
    edges = tuple(low + i * width for i in range(bins + 1))
    counts = [0] * bins
    underflow = 0
    overflow = 0

    for value in values:
        if value < low:
            underflow += 1
        elif value > high:
            overflow += 1
        elif value == high:
            counts[bins - 1] += 1  # Closed final bin.
        else:
            index = int((value - low) / width)
            if index >= bins:  # Guard against float rounding at the top edge.
                index = bins - 1
            counts[index] += 1

    return Histogram(
        low=low,
        high=high,
        width=width,
        edges=edges,
        counts=tuple(counts),
        underflow=underflow,
        overflow=overflow,
    )
