"""Hysteresis-based backpressure decisions for a Digital FTE work queue.

When a queue drains slower than it fills, the runtime should push back on
producers until it recovers. A naive single-threshold rule flaps -- engaging
and releasing on every item that crosses the line. This module uses two
watermarks with hysteresis instead: backpressure *engages* only once depth
reaches the ``high`` watermark and *releases* only once it falls back to the
``low`` watermark, so the state is stable between the two.

:func:`evaluate_backpressure` is the pure decision function: it takes the
current depth and the current engaged/released state and returns the next state
plus the action to take. :class:`BackpressureController` is a thin stateful
wrapper that remembers the last state for callers that prefer to just observe a
depth each tick.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The three possible actions a decision can call for.
APPLY = "apply"
RELEASE = "release"
HOLD = "hold"


def _validate_depth(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _validate_watermarks(high: object, low: object) -> tuple[int, int]:
    high = _validate_depth("high", high)
    low = _validate_depth("low", low)
    if low >= high:
        raise ValueError("low watermark must be strictly below high watermark")
    return high, low


@dataclass(frozen=True)
class BackpressureDecision:
    """The outcome of evaluating one queue-depth observation.

    Attributes:
        depth: The observed queue depth.
        engaged: Whether backpressure is engaged *after* this observation.
        changed: Whether ``engaged`` differs from the prior state.
        action: ``"apply"`` when newly engaging, ``"release"`` when newly
            releasing, ``"hold"`` when the state is unchanged.
    """

    depth: int
    engaged: bool
    changed: bool
    action: str


def evaluate_backpressure(
    depth: int, *, high: int, low: int, engaged: bool
) -> BackpressureDecision:
    """Decide the next backpressure state from a depth observation.

    Args:
        depth: Current queue depth (non-negative integer).
        high: Depth at or above which backpressure engages.
        low: Depth at or below which backpressure releases; must be strictly
            below ``high`` so the two watermarks form a stable band.
        engaged: Whether backpressure is currently engaged.

    Returns:
        A :class:`BackpressureDecision` giving the next state and the action.

    Raises:
        TypeError: If any argument has the wrong type (``bool`` depths/watermarks
            rejected; ``engaged`` must be a real ``bool``).
        ValueError: If a depth or watermark is negative, or ``low >= high``.
    """
    depth = _validate_depth("depth", depth)
    high, low = _validate_watermarks(high, low)
    if not isinstance(engaged, bool):
        raise TypeError("engaged must be a bool")

    if not engaged and depth >= high:
        return BackpressureDecision(depth, engaged=True, changed=True, action=APPLY)
    if engaged and depth <= low:
        return BackpressureDecision(depth, engaged=False, changed=True, action=RELEASE)
    return BackpressureDecision(depth, engaged=engaged, changed=False, action=HOLD)


class BackpressureController:
    """A stateful wrapper around :func:`evaluate_backpressure`.

    Remembers the engaged/released state between observations so callers can
    simply feed each new queue depth to :meth:`observe`. The controller drives a
    single loop from one thread and holds no locks, matching the deterministic
    design of the rest of the package.
    """

    def __init__(self, *, high: int, low: int, engaged: bool = False) -> None:
        self.high, self.low = _validate_watermarks(high, low)
        if not isinstance(engaged, bool):
            raise TypeError("engaged must be a bool")
        self._engaged = engaged

    @property
    def engaged(self) -> bool:
        """Whether backpressure is currently engaged."""
        return self._engaged

    def observe(self, depth: int) -> BackpressureDecision:
        """Feed one depth observation and advance the state, returning it."""
        decision = evaluate_backpressure(
            depth, high=self.high, low=self.low, engaged=self._engaged
        )
        self._engaged = decision.engaged
        return decision
