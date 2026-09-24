"""Build timing spans from supplied timestamps and roll them up.

Profiling a reasoning loop means measuring how long each stage took. A *span*
is one such measurement: a named interval with a start and an end. Crucially,
this module never reads a clock -- the caller supplies ``start`` and ``end``
(taken from whatever injected clock the loop uses), so span construction and
aggregation are pure and fully reproducible in tests.

:func:`make_span` validates and packages a single interval; :func:`rollup`
aggregates many spans into count/total/average/min/max, the shape the telemetry
stage reports.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


def _validate_time(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class Span:
    """A single named timing interval.

    Args:
        name: Label for the span (non-empty).
        start: Start time, in seconds, from the caller's clock.
        end: End time, in seconds; must be ``>= start``.
        duration: ``end - start``; computed by :func:`make_span`.
    """

    name: str
    start: float
    end: float
    duration: float


@dataclass(frozen=True)
class SpanRollup:
    """Aggregate statistics over a collection of spans."""

    count: int
    total: float
    average: float
    minimum: float
    maximum: float


def make_span(name: str, start: float, end: float) -> Span:
    """Build a :class:`Span` from a supplied start and end time.

    Args:
        name: Non-empty label for the span.
        start: Start time in seconds.
        end: End time in seconds; must not precede ``start``.

    Returns:
        A frozen :class:`Span` with ``duration = end - start``.

    Raises:
        TypeError: ``name`` is not a string or a time is not a real number.
        ValueError: ``name`` is empty, a time is non-finite, or ``end < start``.
    """
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    if not name.strip():
        raise ValueError("name must be a non-empty string")
    start = _validate_time("start", start)
    end = _validate_time("end", end)
    if end < start:
        raise ValueError("end must be >= start")
    return Span(name=name, start=start, end=end, duration=end - start)


def rollup(spans: Iterable[Span]) -> SpanRollup:
    """Aggregate ``spans`` into count/total/average/min/max of their durations.

    Args:
        spans: An iterable of :class:`Span` records.

    Returns:
        A :class:`SpanRollup`. An empty input yields all-zero statistics.

    Raises:
        TypeError: an element is not a :class:`Span`.
    """
    durations: list[float] = []
    for span in spans:
        if not isinstance(span, Span):
            raise TypeError("every element must be a Span")
        durations.append(span.duration)

    if not durations:
        return SpanRollup(count=0, total=0.0, average=0.0, minimum=0.0, maximum=0.0)

    total = math.fsum(durations)
    return SpanRollup(
        count=len(durations),
        total=total,
        average=total / len(durations),
        minimum=min(durations),
        maximum=max(durations),
    )
