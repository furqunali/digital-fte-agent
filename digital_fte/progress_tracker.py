"""Completion tracking for long-running Digital FTE tasks.

A run that processes many items (files to scan, tasks to drive, rows to parse)
needs a cheap, exact way to answer "how far along am I?" for status lines and
telemetry. :func:`track_progress` turns a ``completed`` / ``total`` pair into a
:class:`Progress` snapshot -- remaining work, the completion fraction, a
percentage, and a done flag.

The function is pure and deterministic: it reads no clock and holds no state,
so the same inputs always yield the same snapshot. It validates up front that
both counts are real, non-negative whole numbers and that ``completed`` never
exceeds ``total``, so a nonsensical progress value can never be reported.
"""
from __future__ import annotations

from dataclasses import dataclass

# Percentages are rounded to this many places; the raw fraction keeps two more
# so callers that want finer resolution than the percentage still have it.
_PERCENT_PLACES = 4
_FRACTION_PLACES = 6


def _validate_count(name: str, value: object) -> int:
    """Return ``value`` as an int, requiring a non-negative whole number."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


@dataclass(frozen=True)
class Progress:
    """An immutable snapshot of how far a task has progressed.

    Attributes:
        completed: Units of work finished so far.
        total: Total units of work to do.
        remaining: ``total - completed``; never negative.
        fraction: ``completed / total`` in ``0.0..1.0`` (``1.0`` when
            ``total`` is zero -- an empty task is trivially complete).
        percent: ``fraction * 100`` rounded for display.
        is_complete: ``True`` exactly when no work remains.
    """

    completed: int
    total: int
    remaining: int
    fraction: float
    percent: float
    is_complete: bool


def track_progress(completed: int, total: int) -> Progress:
    """Summarise progress as a :class:`Progress` snapshot.

    Args:
        completed: Units of work finished so far (non-negative integer).
        total: Total units of work (non-negative integer, ``>= completed``).

    Returns:
        A :class:`Progress` value. When ``total`` is zero the task is treated
        as complete (fraction ``1.0``) rather than raising, so an empty batch
        renders cleanly on a dashboard.

    Raises:
        TypeError: If either argument is not an ``int`` (``bool`` is rejected).
        ValueError: If either argument is negative, or ``completed > total``.
    """
    completed = _validate_count("completed", completed)
    total = _validate_count("total", total)
    if completed > total:
        raise ValueError("completed must not exceed total")

    remaining = total - completed
    fraction = 1.0 if total == 0 else completed / total
    return Progress(
        completed=completed,
        total=total,
        remaining=remaining,
        fraction=round(fraction, _FRACTION_PLACES),
        percent=round(fraction * 100.0, _PERCENT_PLACES),
        is_complete=remaining == 0,
    )
