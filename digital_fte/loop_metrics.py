"""Fleet-level metrics aggregation across many agent loop runs.

Where :mod:`digital_fte.loop_outcomes` answers "how many loops finished",
this module answers "how efficiently did the fleet of loops work" by rolling
several :class:`~digital_fte.loop.LoopResult` values into a single set of
throughput-oriented metrics: success rate, average iterations, and event
throughput per iteration.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from digital_fte.loop import LoopResult

_ROUND = 4


@dataclass(frozen=True)
class LoopMetrics:
    """Aggregated efficiency metrics for a batch of loop runs.

    Attributes:
        runs: Total number of loop results aggregated.
        successes: Runs whose ``status`` is ``"completed"``.
        failures: Runs that did not complete.
        success_rate: ``successes / runs`` rounded to four places (0.0 if empty).
        total_iterations: Sum of ``iterations`` across every run.
        avg_iterations: Mean iterations per run (0.0 if empty).
        avg_iterations_to_success: Mean iterations across completed runs only
            (0.0 when no run completed).
        total_events: Sum of recorded agent events across every run.
        throughput: Agent events per iteration, i.e. how much work each loop
            iteration accomplished on average (0.0 when no iterations ran).
    """

    runs: int
    successes: int
    failures: int
    success_rate: float
    total_iterations: int
    avg_iterations: float
    avg_iterations_to_success: float
    total_events: int
    throughput: float


def aggregate_loop_metrics(results: Iterable[LoopResult]) -> LoopMetrics:
    """Aggregate loop results into fleet-level efficiency metrics.

    Args:
        results: An iterable of :class:`~digital_fte.loop.LoopResult` values.

    Returns:
        A :class:`LoopMetrics` snapshot. Ratios collapse to ``0.0`` rather than
        raising when their denominator is zero (empty input, zero iterations, or
        no successful run), keeping the metric safe to render on dashboards.

    Raises:
        TypeError: If any element is not a ``LoopResult``.
        ValueError: If any result reports a negative iteration count.
    """
    items = list(results)
    for item in items:
        if not isinstance(item, LoopResult):
            raise TypeError("results must contain LoopResult values")
        if item.iterations < 0:
            raise ValueError("LoopResult.iterations must not be negative")

    runs = len(items)
    successes = sum(item.status == "completed" for item in items)
    failures = runs - successes

    total_iterations = sum(item.iterations for item in items)
    total_events = sum(len(item.events) for item in items)

    completed_iterations = sum(
        item.iterations for item in items if item.status == "completed"
    )

    return LoopMetrics(
        runs=runs,
        successes=successes,
        failures=failures,
        success_rate=_ratio(successes, runs),
        total_iterations=total_iterations,
        avg_iterations=_ratio(total_iterations, runs),
        avg_iterations_to_success=_ratio(completed_iterations, successes),
        total_events=total_events,
        throughput=_ratio(total_events, total_iterations),
    )


def _ratio(numerator: int, denominator: int) -> float:
    """Return ``numerator / denominator`` rounded, or ``0.0`` when undefined."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, _ROUND)
