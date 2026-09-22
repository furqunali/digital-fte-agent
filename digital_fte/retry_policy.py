"""Deterministic retry policy with exponential backoff (no random jitter).

The Digital FTE action stage talks to flaky things: a watched folder that is
mid-write, a downstream service that returns a transient error, a lock that is
briefly held. Naive retries either give up too early or hammer the resource.

This module gives the reasoning loop a *reproducible* retry schedule. Unlike the
common "backoff + random jitter" recipe, the schedule here is fully
deterministic: the same :class:`RetryPolicy` always produces the same sequence
of delays, so a run can be replayed, asserted on in tests, and reported in loop
telemetry without a seeded RNG.

Timing model
------------
Attempts are numbered from ``1``. Attempt ``1`` is the initial try and has no
preceding delay. The delay *before* attempt ``n`` (for ``n >= 2``) is::

    min(base_delay * factor ** (n - 2), max_delay)

so with ``base_delay=1``, ``factor=2`` the waits before attempts 2, 3, 4 are
``1, 2, 4`` seconds, optionally clamped by ``max_delay``.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when every attempt allowed by the policy has failed.

    The final underlying exception is available as :attr:`last_exception` and is
    also chained via ``__cause__`` so tracebacks point at the real failure.
    """

    def __init__(self, attempts: int, last_exception: BaseException) -> None:
        super().__init__(
            f"all {attempts} attempt(s) failed; "
            f"last error: {type(last_exception).__name__}: {last_exception}"
        )
        self.attempts = attempts
        self.last_exception = last_exception


@dataclass(frozen=True)
class AttemptRecord:
    """Telemetry for a single failed attempt.

    ``delay`` is the wait that preceded the attempt (``0.0`` for attempt 1).
    """

    attempt: int
    delay: float
    error_type: str
    error: str


@dataclass(frozen=True)
class RetryOutcome:
    """The result of a successful :meth:`RetryPolicy.execute` call."""

    value: object
    attempts: int
    failures: tuple[AttemptRecord, ...] = field(default_factory=tuple)

    @property
    def retried(self) -> bool:
        """``True`` when the call succeeded only after one or more retries."""
        return bool(self.failures)


def _validate_number(name: str, value: object, *, minimum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):  # NaN is never ordered, guard explicitly.
        raise ValueError(f"{name} must not be NaN")
    if number < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return number


@dataclass(frozen=True)
class RetryPolicy:
    """A reproducible exponential-backoff schedule for the action stage.

    Args:
        max_attempts: Total tries allowed, including the first (``>= 1``).
        base_delay: Seconds to wait before attempt 2 (``>= 0``).
        factor: Growth multiplier applied per subsequent attempt (``>= 1``).
        max_delay: Optional per-attempt ceiling in seconds (``> 0`` or ``None``).

    All fields are validated on construction; an instance is immutable and its
    :meth:`schedule` is a pure function of these values.
    """

    max_attempts: int = 3
    base_delay: float = 0.5
    factor: float = 2.0
    max_delay: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        object.__setattr__(self, "base_delay", _validate_number("base_delay", self.base_delay, minimum=0.0))
        object.__setattr__(self, "factor", _validate_number("factor", self.factor, minimum=1.0))
        if self.max_delay is not None:
            capped = _validate_number("max_delay", self.max_delay, minimum=0.0)
            if capped <= 0.0:
                raise ValueError("max_delay must be > 0 when provided")
            object.__setattr__(self, "max_delay", capped)

    def delay_before(self, attempt: int) -> float:
        """Return the deterministic wait, in seconds, before ``attempt``.

        Attempt ``1`` always returns ``0.0``. Raises :class:`TypeError` for a
        non-integer attempt and :class:`ValueError` for one outside
        ``1..max_attempts``.
        """
        if isinstance(attempt, bool) or not isinstance(attempt, int):
            raise TypeError("attempt must be an integer")
        if not 1 <= attempt <= self.max_attempts:
            raise ValueError(f"attempt must be in 1..{self.max_attempts}")
        if attempt == 1:
            return 0.0
        raw = self.base_delay * (self.factor ** (attempt - 2))
        if self.max_delay is not None:
            return min(raw, self.max_delay)
        return raw

    def schedule(self) -> tuple[float, ...]:
        """Return the full per-attempt delay sequence, length ``max_attempts``.

        Index ``i`` is the delay before attempt ``i + 1``; element ``0`` is
        always ``0.0``.
        """
        return tuple(self.delay_before(attempt) for attempt in range(1, self.max_attempts + 1))

    def total_delay(self) -> float:
        """Return the sum of all scheduled waits (best-case worst-path total)."""
        return sum(self.schedule())

    def execute(
        self,
        func: Callable[[], T],
        *,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
        sleep: Callable[[float], None] = time.sleep,
    ) -> RetryOutcome:
        """Call ``func`` under the policy, retrying on ``retry_on`` failures.

        ``func`` is invoked with no arguments. Before each attempt after the
        first the scheduled delay is passed to ``sleep`` (injectable so tests
        need not actually wait). An exception that is not an instance of any
        type in ``retry_on`` propagates immediately without consuming further
        attempts. If every allowed attempt raises a retriable error,
        :class:`RetryExhausted` is raised with the last one chained.

        Returns a :class:`RetryOutcome` carrying the value, the attempt count,
        and a record of any intermediate failures for loop telemetry.
        """
        if not callable(func):
            raise TypeError("func must be callable")
        if not isinstance(retry_on, tuple) or not retry_on:
            raise TypeError("retry_on must be a non-empty tuple of exception types")
        for exc_type in retry_on:
            if not (isinstance(exc_type, type) and issubclass(exc_type, BaseException)):
                raise TypeError("retry_on entries must be exception types")
        if not callable(sleep):
            raise TypeError("sleep must be callable")

        failures: list[AttemptRecord] = []
        last_exception: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            delay = self.delay_before(attempt)
            if delay > 0.0:
                sleep(delay)
            try:
                value = func()
            except retry_on as exc:
                last_exception = exc
                failures.append(
                    AttemptRecord(
                        attempt=attempt,
                        delay=delay,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                )
                continue
            return RetryOutcome(value=value, attempts=attempt, failures=tuple(failures))

        assert last_exception is not None
        raise RetryExhausted(self.max_attempts, last_exception) from last_exception
