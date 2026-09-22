"""A circuit breaker guarding the Digital FTE action stage against flaky calls.

The reasoning loop repeatedly drives an action -- writing to a watched folder,
poking a downstream service, taking a lock. When such a dependency starts
failing hard, retrying every task against it wastes the run's time budget and
can make an outage worse. A circuit breaker short-circuits that: after enough
consecutive failures it *opens* and fails fast, gives the dependency a cooling
-off window, then lets a single probe through to decide whether to recover.

State machine
-------------
The breaker is a classic three-state machine::

    CLOSED  --failures reach threshold-->  OPEN
    OPEN    --recovery_timeout elapses -->  HALF_OPEN   (lazy, clock-driven)
    HALF_OPEN --probe succeeds enough  -->  CLOSED
    HALF_OPEN --any probe fails        -->  OPEN        (cooldown restarts)

* **CLOSED** -- calls pass through. Each success resets the consecutive-failure
  counter; ``failure_threshold`` consecutive failures trip the breaker OPEN.
* **OPEN** -- calls are rejected immediately with :class:`CircuitOpenError`
  without touching the dependency, until ``recovery_timeout`` seconds have
  elapsed since the trip, after which the breaker moves to HALF_OPEN.
* **HALF_OPEN** -- a limited number of probe calls are admitted. Once
  ``success_threshold`` probes have succeeded the breaker closes and forgets the
  outage; a single probe failure re-opens it and restarts the cooldown.

Time is read through an injectable monotonic ``clock`` (default
:func:`time.monotonic`) so recovery timing is fully testable without sleeping.
The breaker is deliberately mutable -- it *is* the run's live state -- but every
transition goes through one guarded path so the invariants above always hold.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    """The three states of the breaker.

    Inherits from :class:`str` so a state compares equal to its wire value
    (``CircuitState.OPEN == "open"``) and serialises cleanly into telemetry.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the breaker is not accepting it.

    ``retry_after`` is the number of seconds until the breaker is expected to
    admit a probe again -- ``0.0`` when the caller merely lost the race for a
    limited half-open probe slot.
    """

    def __init__(self, retry_after: float) -> None:
        super().__init__(
            f"circuit is open; retry after {retry_after:.3f}s"
        )
        self.retry_after = retry_after


@dataclass(frozen=True)
class BreakerSnapshot:
    """An immutable, serialisable view of the breaker for loop telemetry."""

    state: CircuitState
    consecutive_failures: int
    half_open_successes: int
    total_calls: int
    total_failures: int
    total_rejections: int
    opened_count: int
    time_until_retry: float | None


def _validate_positive_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):  # NaN compares false against everything; guard it.
        raise ValueError(f"{name} must not be NaN")
    if number <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return number


def _validate_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


class CircuitBreaker:
    """A three-state circuit breaker for a single flaky dependency.

    Args:
        failure_threshold: Consecutive CLOSED-state failures that trip the
            breaker OPEN (``>= 1``).
        recovery_timeout: Seconds the breaker stays OPEN before admitting a
            half-open probe (``> 0``).
        success_threshold: Successful half-open probes required to close again
            (``>= 1``). Also caps the number of concurrent probes admitted.
        record_on: Exception types that count as dependency failures. Anything
            outside this tuple propagates without affecting breaker state, so a
            programming error never trips the breaker.
        clock: Zero-argument monotonic time source in seconds. Injectable for
            tests; must be non-decreasing.

    All arguments are validated on construction.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 1,
        record_on: tuple[type[BaseException], ...] = (Exception,),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = _validate_positive_int(
            "failure_threshold", failure_threshold
        )
        self.recovery_timeout = _validate_positive_number(
            "recovery_timeout", recovery_timeout
        )
        self.success_threshold = _validate_positive_int(
            "success_threshold", success_threshold
        )
        if not isinstance(record_on, tuple) or not record_on:
            raise TypeError("record_on must be a non-empty tuple of exception types")
        for exc_type in record_on:
            if not (isinstance(exc_type, type) and issubclass(exc_type, BaseException)):
                raise TypeError("record_on entries must be exception types")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.record_on = record_on
        self._clock = clock

        # Live state.
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._probes_in_flight = 0
        self._opened_at: float | None = None

        # Cumulative counters for telemetry.
        self._total_calls = 0
        self._total_failures = 0
        self._total_rejections = 0
        self._opened_count = 0

    # -- state inspection ----------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Return the current state, applying any due OPEN -> HALF_OPEN move.

        Reading the state is what lazily advances an expired OPEN breaker into
        HALF_OPEN, so callers never observe a stale ``OPEN`` past its recovery
        window.
        """
        self._maybe_recover()
        return self._state

    @property
    def consecutive_failures(self) -> int:
        """Consecutive CLOSED-state failures accrued toward the threshold."""
        return self._consecutive_failures

    def time_until_retry(self) -> float | None:
        """Seconds until an OPEN breaker will admit a probe, else ``None``.

        Returns ``0.0`` when the recovery window has already elapsed but the
        breaker has not yet been advanced, and ``None`` whenever the breaker is
        not OPEN.
        """
        if self._state is not CircuitState.OPEN or self._opened_at is None:
            return None
        elapsed = self._clock() - self._opened_at
        return max(0.0, self.recovery_timeout - elapsed)

    def allows_call(self) -> bool:
        """Return whether a call would be admitted right now.

        This has the side effect of recovering an expired OPEN breaker (see
        :attr:`state`) so it stays consistent with :meth:`call`.
        """
        current = self.state  # triggers _maybe_recover
        if current is CircuitState.OPEN:
            return False
        if current is CircuitState.HALF_OPEN:
            return self._probes_in_flight < self.success_threshold
        return True

    def snapshot(self) -> BreakerSnapshot:
        """Return an immutable telemetry snapshot of the breaker."""
        return BreakerSnapshot(
            state=self.state,  # recover first so the snapshot is current
            consecutive_failures=self._consecutive_failures,
            half_open_successes=self._half_open_successes,
            total_calls=self._total_calls,
            total_failures=self._total_failures,
            total_rejections=self._total_rejections,
            opened_count=self._opened_count,
            time_until_retry=self.time_until_retry(),
        )

    # -- driving the breaker -------------------------------------------------

    def call(self, func: Callable[[], T]) -> T:
        """Invoke ``func`` under the breaker, or fail fast if it is not open.

        ``func`` is called with no arguments. When the breaker is OPEN (and the
        recovery window has not elapsed) or all half-open probe slots are taken,
        :class:`CircuitOpenError` is raised and ``func`` is never called. A
        successful call is recorded via :meth:`record_success`; a failure whose
        type is in ``record_on`` is recorded via :meth:`record_failure` and then
        re-raised. Exceptions outside ``record_on`` propagate untouched.
        """
        if not callable(func):
            raise TypeError("func must be callable")

        if not self.allows_call():
            self._total_rejections += 1
            raise CircuitOpenError(self.time_until_retry() or 0.0)

        # A half-open admission holds a probe slot for the duration of the call.
        probing = self._state is CircuitState.HALF_OPEN
        if probing:
            self._probes_in_flight += 1
        self._total_calls += 1
        try:
            result = func()
        except self.record_on:
            self._total_failures += 1
            if probing:
                self._probes_in_flight -= 1
            self._on_failure()
            raise
        except BaseException:
            # Not a recorded failure: release the probe slot but leave state and
            # counters untouched -- this outcome is invisible to the breaker.
            if probing:
                self._probes_in_flight -= 1
            self._total_calls -= 1
            raise
        else:
            if probing:
                self._probes_in_flight -= 1
            self._on_success()
            return result

    def record_success(self) -> None:
        """Record a successful action without routing it through :meth:`call`.

        Provided for callers that manage the invocation themselves; keeps the
        same state transitions as a successful :meth:`call`.
        """
        self._maybe_recover()
        self._on_success()

    def record_failure(self) -> None:
        """Record a failed action without routing it through :meth:`call`.

        Mirrors :meth:`record_success` for hand-rolled invocation paths.
        """
        self._maybe_recover()
        self._on_failure()

    def reset(self) -> None:
        """Force the breaker back to a clean CLOSED state.

        Cumulative telemetry counters are preserved; only the live state machine
        is cleared. Useful when an operator has manually remediated the
        dependency mid-run.
        """
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._probes_in_flight = 0
        self._opened_at = None

    # -- internal transitions ------------------------------------------------

    def _maybe_recover(self) -> None:
        """Advance an OPEN breaker to HALF_OPEN once its window has elapsed."""
        if self._state is not CircuitState.OPEN or self._opened_at is None:
            return
        if self._clock() - self._opened_at >= self.recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            self._half_open_successes = 0
            self._probes_in_flight = 0

    def _on_success(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.success_threshold:
                self._close()
        else:
            # A success in CLOSED clears any partial failure streak.
            self._consecutive_failures = 0

    def _on_failure(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            # The probe failed: the dependency is still unhealthy, re-open.
            self._trip()
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
        self._opened_count += 1
        self._half_open_successes = 0
        self._probes_in_flight = 0

    def _close(self) -> None:
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._probes_in_flight = 0
        self._opened_at = None
