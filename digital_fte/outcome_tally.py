"""Tally task outcomes into counts and rates for run telemetry.

At the end of a run (or a window within one) the loop reports how work turned
out: how many tasks succeeded, how many failed, how many were retried. This
module reduces a sequence of outcome labels to a frozen record of per-outcome
counts plus their rates as fractions of the total. It is a pure function of the
input sequence -- no clock, no randomness.

Only three outcome labels are recognised (:data:`SUCCESS`, :data:`FAILURE`,
:data:`RETRY`); any other value is rejected up front so a typo cannot silently
skew a report.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

SUCCESS = "success"
FAILURE = "failure"
RETRY = "retry"

OUTCOMES = (SUCCESS, FAILURE, RETRY)


@dataclass(frozen=True)
class Tally:
    """Counts and rates over a sequence of outcomes.

    Rates are fractions in ``0.0..1.0`` of the total; when ``total`` is zero all
    rates are ``0.0``.
    """

    success: int
    failure: int
    retry: int
    total: int
    success_rate: float
    failure_rate: float
    retry_rate: float

    @property
    def counts(self) -> dict:
        """Return the raw counts as a ``{outcome: count}`` mapping."""
        return {SUCCESS: self.success, FAILURE: self.failure, RETRY: self.retry}


def tally(outcomes: Iterable[str]) -> Tally:
    """Count ``outcomes`` and compute per-outcome rates.

    Args:
        outcomes: An iterable of outcome labels, each one of :data:`OUTCOMES`.

    Returns:
        A frozen :class:`Tally`. An empty input yields all-zero counts and
        rates.

    Raises:
        TypeError: an element is not a string.
        ValueError: an element is not one of the recognised outcome labels.
    """
    counts = {SUCCESS: 0, FAILURE: 0, RETRY: 0}
    for outcome in outcomes:
        if not isinstance(outcome, str):
            raise TypeError("each outcome must be a string")
        if outcome not in counts:
            raise ValueError(
                f"unknown outcome {outcome!r}; expected one of {OUTCOMES}"
            )
        counts[outcome] += 1

    total = counts[SUCCESS] + counts[FAILURE] + counts[RETRY]
    if total == 0:
        return Tally(0, 0, 0, 0, 0.0, 0.0, 0.0)
    return Tally(
        success=counts[SUCCESS],
        failure=counts[FAILURE],
        retry=counts[RETRY],
        total=total,
        success_rate=counts[SUCCESS] / total,
        failure_rate=counts[FAILURE] / total,
        retry_rate=counts[RETRY] / total,
    )
