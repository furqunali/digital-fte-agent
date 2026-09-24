"""Summarise a series of queue-depth samples.

The Digital FTE work queue is polled periodically and its depth recorded. To
tell whether the queue is keeping up or backing up, those samples are reduced to
a few headline statistics: the peak depth, the average, and a p95 that ignores
the odd spike. :func:`summarize_queue_depth` computes them purely from the
supplied samples -- no clock, no randomness -- so a given series always yields
the same summary.

The p95 uses the nearest-rank method (rank ``ceil(0.95 * n)``), returning a depth
that actually occurred in the series.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


def _coerce_samples(samples: Iterable[float]) -> list[float]:
    """Validate ``samples`` into a non-empty list of finite, non-negative floats."""
    if isinstance(samples, (str, bytes)):
        raise TypeError("samples must be an iterable of numbers, not a string")
    try:
        items = list(samples)
    except TypeError as exc:
        raise TypeError("samples must be iterable") from exc
    if not items:
        raise ValueError("samples must be non-empty")
    out: list[float] = []
    for value in items:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("queue-depth samples must be real numbers")
        number = float(value)
        if math.isnan(number):
            raise ValueError("queue-depth samples must not be NaN")
        if math.isinf(number):
            raise ValueError("queue-depth samples must be finite")
        if number < 0.0:
            raise ValueError("queue-depth samples must be >= 0")
        out.append(number)
    return out


def _nearest_rank(sorted_values: list[float], q: float) -> float:
    """Return the nearest-rank ``q``-percentile of an ascending list."""
    n = len(sorted_values)
    rank = math.ceil(q / 100.0 * n)
    if rank < 1:
        rank = 1
    if rank > n:
        rank = n
    return sorted_values[rank - 1]


@dataclass(frozen=True)
class QueueDepthSummary:
    """Headline statistics for a series of queue-depth samples.

    Args:
        count: Number of samples.
        min: Smallest observed depth.
        max: Largest observed depth (the peak).
        avg: Arithmetic mean depth.
        p95: Nearest-rank 95th percentile depth.
    """

    count: int
    min: float
    max: float
    avg: float
    p95: float


def summarize_queue_depth(samples: Iterable[float]) -> QueueDepthSummary:
    """Summarise ``samples`` into a :class:`QueueDepthSummary`.

    Args:
        samples: A non-empty iterable of finite, non-negative depths.
    """
    values = _coerce_samples(samples)
    ordered = sorted(values)
    return QueueDepthSummary(
        count=len(values),
        min=ordered[0],
        max=ordered[-1],
        avg=math.fsum(values) / len(values),
        p95=_nearest_rank(ordered, 95.0),
    )
