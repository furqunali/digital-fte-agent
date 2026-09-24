"""Nearest-rank percentiles over a numeric sample.

Latency and cost telemetry is far better summarised by percentiles than by a
mean: p99 tells you the tail users actually feel. This module implements the
*nearest-rank* method, which is exact, order-statistic based, and returns a
value that genuinely appears in the sample -- no interpolation, so results are
deterministic and easy to reason about.

For a sorted sample of ``n`` values the rank for quantile ``q`` (a percentage in
``[0, 100]``) is ``ceil(q / 100 * n)``, clamped to at least ``1``; the result is
the value at that 1-based rank. Thus ``q = 0`` yields the minimum and ``q = 100``
the maximum.
"""
from __future__ import annotations

import math
from collections.abc import Iterable


def _require_quantile(name: str, value: object) -> float:
    """Return ``value`` as a float within ``[0, 100]``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if not 0.0 <= number <= 100.0:
        raise ValueError(f"{name} must be within 0..100")
    return number


def _coerce_sample(sample: Iterable[float]) -> list[float]:
    """Validate ``sample`` into a non-empty list of finite floats."""
    if isinstance(sample, (str, bytes)):
        raise TypeError("sample must be an iterable of numbers, not a string")
    try:
        items = list(sample)
    except TypeError as exc:
        raise TypeError("sample must be iterable") from exc
    if not items:
        raise ValueError("sample must be non-empty")
    out: list[float] = []
    for value in items:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("sample values must be real numbers")
        number = float(value)
        if math.isnan(number):
            raise ValueError("sample values must not be NaN")
        if math.isinf(number):
            raise ValueError("sample values must be finite")
        out.append(number)
    return out


def percentile(sample: Iterable[float], q: float) -> float:
    """Return the nearest-rank ``q``-th percentile of ``sample``.

    Args:
        sample: A non-empty iterable of finite real numbers.
        q: The desired percentile as a percentage in ``[0, 100]``.

    ``q = 0`` returns the minimum and ``q = 100`` the maximum.
    """
    q = _require_quantile("q", q)
    values = sorted(_coerce_sample(sample))
    n = len(values)
    if q <= 0.0:
        return values[0]
    rank = math.ceil(q / 100.0 * n)
    if rank < 1:
        rank = 1
    if rank > n:
        rank = n
    return values[rank - 1]


def p50(sample: Iterable[float]) -> float:
    """Return the median (50th percentile) by nearest rank."""
    return percentile(sample, 50.0)


def p90(sample: Iterable[float]) -> float:
    """Return the 90th percentile by nearest rank."""
    return percentile(sample, 90.0)


def p99(sample: Iterable[float]) -> float:
    """Return the 99th percentile by nearest rank."""
    return percentile(sample, 99.0)
