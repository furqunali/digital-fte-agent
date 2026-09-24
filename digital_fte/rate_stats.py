"""Success-rate and failure-streak statistics for a Digital FTE run.

Given an ordered list of per-attempt outcomes (``True`` for success, ``False``
for failure), :func:`compute_rate_stats` summarises reliability: the overall
success and failure rates plus the longest run of consecutive failures (a
signal of a sustained outage rather than sporadic flakiness) and the longest
run of consecutive successes. The trailing failure streak -- failures at the
very end of the sequence -- is also reported, since that is what a live guard
watches to decide whether to trip.

The function is pure and deterministic and validates that every element is a
real ``bool`` (integers ``0``/``1`` are rejected) so the outcome list cannot be
silently misinterpreted.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

_ROUND = 4


@dataclass(frozen=True)
class RateStats:
    """Reliability statistics for a sequence of outcomes.

    Attributes:
        total: Number of outcomes considered.
        successes: Count of ``True`` outcomes.
        failures: Count of ``False`` outcomes.
        success_rate: ``successes / total`` rounded (``0.0`` when empty).
        failure_rate: ``failures / total`` rounded (``0.0`` when empty).
        longest_success_streak: Longest run of consecutive successes.
        longest_failure_streak: Longest run of consecutive failures.
        current_failure_streak: Consecutive failures at the end of the sequence.
    """

    total: int
    successes: int
    failures: int
    success_rate: float
    failure_rate: float
    longest_success_streak: int
    longest_failure_streak: int
    current_failure_streak: int


def compute_rate_stats(outcomes: Iterable[bool]) -> RateStats:
    """Summarise a sequence of boolean outcomes.

    Args:
        outcomes: An iterable of ``bool`` outcomes (``True`` = success).

    Returns:
        A :class:`RateStats` snapshot. Rates collapse to ``0.0`` on empty input
        rather than raising.

    Raises:
        TypeError: If any element is not a real ``bool`` (``0``/``1`` and other
            ints are rejected).
    """
    items = list(outcomes)
    for item in items:
        if not isinstance(item, bool):
            raise TypeError("outcomes must contain only bool values")

    total = len(items)
    successes = sum(1 for item in items if item)
    failures = total - successes

    longest_success = 0
    longest_failure = 0
    current_success = 0
    current_failure = 0
    for item in items:
        if item:
            current_success += 1
            current_failure = 0
        else:
            current_failure += 1
            current_success = 0
        longest_success = max(longest_success, current_success)
        longest_failure = max(longest_failure, current_failure)

    # current_failure now holds the trailing failure streak.
    return RateStats(
        total=total,
        successes=successes,
        failures=failures,
        success_rate=_ratio(successes, total),
        failure_rate=_ratio(failures, total),
        longest_success_streak=longest_success,
        longest_failure_streak=longest_failure,
        current_failure_streak=current_failure,
    )


def _ratio(numerator: int, denominator: int) -> float:
    """Return ``numerator / denominator`` rounded, or ``0.0`` when undefined."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, _ROUND)
