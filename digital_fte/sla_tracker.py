"""Count SLA breaches across a batch of latencies.

An SLA such as "responses within 200ms" is measured by comparing each observed
latency against a threshold. :func:`track_sla` counts how many latencies breach
the threshold and reports the breach rate alongside the complementary compliance
figures. It is a pure function of the latencies and the threshold -- no clock,
no randomness -- so the same batch always yields the same report.

A latency *breaches* when it is strictly greater than the threshold; a latency
exactly equal to the threshold is compliant (it met the deadline).
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


def _require_threshold(name: str, value: object) -> float:
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


def _coerce_latencies(latencies: Iterable[float]) -> list[float]:
    """Validate ``latencies`` into a list of finite, non-negative floats."""
    if isinstance(latencies, (str, bytes)):
        raise TypeError("latencies must be an iterable of numbers, not a string")
    try:
        items = list(latencies)
    except TypeError as exc:
        raise TypeError("latencies must be iterable") from exc
    out: list[float] = []
    for value in items:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("latencies must be real numbers")
        number = float(value)
        if math.isnan(number):
            raise ValueError("latencies must not be NaN")
        if math.isinf(number):
            raise ValueError("latencies must be finite")
        if number < 0.0:
            raise ValueError("latencies must be >= 0")
        out.append(number)
    return out


@dataclass(frozen=True)
class SLAReport:
    """The outcome of checking latencies against an SLA threshold.

    Args:
        total: Number of latencies checked.
        breaches: How many exceeded the threshold.
        threshold: The SLA threshold used.
        breach_rate: ``breaches / total`` (``0.0`` for an empty batch).
    """

    total: int
    breaches: int
    threshold: float
    breach_rate: float

    @property
    def compliant(self) -> int:
        """Number of latencies that met the SLA."""
        return self.total - self.breaches

    @property
    def compliance_rate(self) -> float:
        """Fraction of latencies that met the SLA (``1.0`` for an empty batch)."""
        return 1.0 - self.breach_rate


def track_sla(latencies: Iterable[float], threshold: float) -> SLAReport:
    """Return an :class:`SLAReport` for ``latencies`` against ``threshold``.

    Args:
        latencies: An iterable of finite, non-negative latencies (may be empty).
        threshold: The SLA threshold; a latency breaches when strictly greater.

    An empty batch yields a breach rate of ``0.0`` (nothing breached).
    """
    threshold = _require_threshold("threshold", threshold)
    values = _coerce_latencies(latencies)
    total = len(values)
    breaches = sum(1 for value in values if value > threshold)
    breach_rate = breaches / total if total else 0.0
    return SLAReport(
        total=total,
        breaches=breaches,
        threshold=threshold,
        breach_rate=breach_rate,
    )
