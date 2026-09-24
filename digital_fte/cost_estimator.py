"""Estimate model spend from token counts and per-1k rates.

Providers price LLM usage per thousand tokens, usually with a different rate for
prompt (input) tokens and completion (output) tokens. :func:`estimate_cost`
turns a token count and those rates into a :class:`CostBreakdown`. It is a pure
arithmetic function -- no clock, no rounding surprises beyond ordinary float
maths -- so the same inputs always produce the same estimate for budgeting and
telemetry.

Costs are returned in whatever currency unit the rates are expressed in; the
module is unit-agnostic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

_PER_1K = 1000.0


def _require_count(name: str, value: object) -> int:
    """Return ``value`` as a non-negative int (token count)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _require_rate(name: str, value: object) -> float:
    """Return ``value`` as a finite, non-negative float (a price)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if number < 0.0:
        raise ValueError(f"{name} must be >= 0")
    return number


@dataclass(frozen=True)
class CostBreakdown:
    """The estimated cost of a single model call, split by direction.

    Args:
        prompt_tokens: Input tokens billed.
        completion_tokens: Output tokens billed.
        prompt_cost: Cost attributable to the prompt tokens.
        completion_cost: Cost attributable to the completion tokens.
        total_cost: ``prompt_cost + completion_cost``.
    """

    prompt_tokens: int
    completion_tokens: int
    prompt_cost: float
    completion_cost: float
    total_cost: float

    @property
    def total_tokens(self) -> int:
        """The combined prompt and completion token count."""
        return self.prompt_tokens + self.completion_tokens


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    prompt_rate_per_1k: float,
    completion_rate_per_1k: float,
) -> CostBreakdown:
    """Estimate the cost of a call from token counts and per-1k rates.

    Args:
        prompt_tokens: Input token count (``>= 0``).
        completion_tokens: Output token count (``>= 0``).
        prompt_rate_per_1k: Price per 1000 prompt tokens (``>= 0``).
        completion_rate_per_1k: Price per 1000 completion tokens (``>= 0``).

    Returns a :class:`CostBreakdown` where each cost is
    ``tokens / 1000 * rate``.
    """
    prompt_tokens = _require_count("prompt_tokens", prompt_tokens)
    completion_tokens = _require_count("completion_tokens", completion_tokens)
    prompt_rate = _require_rate("prompt_rate_per_1k", prompt_rate_per_1k)
    completion_rate = _require_rate("completion_rate_per_1k", completion_rate_per_1k)

    prompt_cost = prompt_tokens / _PER_1K * prompt_rate
    completion_cost = completion_tokens / _PER_1K * completion_rate
    return CostBreakdown(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        prompt_cost=prompt_cost,
        completion_cost=completion_cost,
        total_cost=prompt_cost + completion_cost,
    )
