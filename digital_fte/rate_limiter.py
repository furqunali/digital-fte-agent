"""Token-bucket rate limiter for throttling Digital FTE actions.

The action stage of a reasoning loop can fire external side effects far faster
than downstream systems tolerate: hammering an API, re-touching a watched
folder, or reopening a lock in a tight retry loop. A token bucket smooths that
traffic -- it permits short bursts up to a fixed *capacity* while enforcing a
sustained average *refill rate* over time.

Design
------
The bucket holds up to ``capacity`` tokens and refills continuously at
``refill_rate`` tokens per second. Acquiring an action costs one or more
tokens; a request is only admitted when enough tokens are present, so the
long-run admission rate can never exceed ``refill_rate`` while allowing a burst
of up to ``capacity`` back-to-back actions when the bucket is full.

Time is injected as a monotonic ``clock`` callable (defaulting to
:func:`time.monotonic`) exactly like :class:`~digital_fte.retry_policy.RetryPolicy`
injects ``sleep`` -- so refill behaviour is fully reproducible in tests without
real waiting. Refill is computed lazily from elapsed clock time on each call
rather than by a background thread, which keeps the limiter deterministic and
free of concurrency machinery.

Every admitted or rejected decision is recorded so a run can report exactly how
much it was throttled, feeding the loop telemetry stage.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass


def _validate_positive_number(name: str, value: object) -> float:
    """Return ``value`` as a float, requiring a real, finite, positive number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):  # NaN compares false against every bound.
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if number <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return number


def _validate_token_count(name: str, value: object) -> int:
    """Return ``value`` as an int, requiring a positive whole number of tokens."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


class RateLimitExceeded(Exception):
    """Raised when :meth:`TokenBucket.acquire` cannot admit a request.

    :attr:`tokens` is the number requested and :attr:`retry_after` is the
    deterministic wait, in seconds, after which the request would succeed given
    no intervening acquisitions.
    """

    def __init__(self, tokens: int, retry_after: float) -> None:
        super().__init__(
            f"rate limit exceeded: {tokens} token(s) requested; "
            f"retry after {retry_after:.6g}s"
        )
        self.tokens = tokens
        self.retry_after = retry_after


@dataclass(frozen=True)
class AcquireResult:
    """Outcome of a single acquire attempt, for loop telemetry.

    Args:
        allowed: Whether the request was admitted.
        tokens: How many tokens the request asked for.
        remaining: Tokens left in the bucket immediately after the decision.
        retry_after: Wait, in seconds, until the request *would* succeed;
            ``0.0`` when it was allowed.
    """

    allowed: bool
    tokens: int
    remaining: float
    retry_after: float


class TokenBucket:
    """A deterministic token-bucket rate limiter with lazy refill.

    Args:
        capacity: Maximum tokens the bucket can hold; also the largest burst
            admissible at once (must be a positive number).
        refill_rate: Tokens added per second of elapsed clock time (positive).
        initial_tokens: Tokens present at construction; defaults to a full
            bucket (``capacity``). Must be within ``0..capacity``.
        clock: Zero-arg callable returning a monotonically non-decreasing time
            in seconds; injected for reproducible tests.

    The bucket is not thread-safe by design: the reasoning loop drives it from a
    single thread, and keeping it lock-free preserves the deterministic,
    replayable behaviour the rest of the package relies on.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        *,
        initial_tokens: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.capacity = _validate_positive_number("capacity", capacity)
        self.refill_rate = _validate_positive_number("refill_rate", refill_rate)
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._clock = clock

        if initial_tokens is None:
            tokens = self.capacity
        else:
            if isinstance(initial_tokens, bool) or not isinstance(
                initial_tokens, (int, float)
            ):
                raise TypeError("initial_tokens must be a real number")
            tokens = float(initial_tokens)
            if math.isnan(tokens):
                raise ValueError("initial_tokens must not be NaN")
            if tokens < 0.0 or tokens > self.capacity:
                raise ValueError("initial_tokens must be within 0..capacity")
        self._tokens = tokens

        now = self._now()
        self._last_refill = now
        self._allowed_count = 0
        self._rejected_count = 0

    # -- introspection -------------------------------------------------------

    @property
    def allowed_count(self) -> int:
        """Number of requests admitted over this bucket's lifetime."""
        return self._allowed_count

    @property
    def rejected_count(self) -> int:
        """Number of requests refused over this bucket's lifetime."""
        return self._rejected_count

    def available_tokens(self) -> float:
        """Return the tokens available *now*, after applying lazy refill.

        This advances the internal clock reading and accrues refill, but never
        spends tokens, so it is safe to call for reporting.
        """
        self._refill()
        return self._tokens

    def time_until_available(self, tokens: int = 1) -> float:
        """Return seconds until ``tokens`` could be acquired, without spending.

        Returns ``0.0`` when enough tokens are already present. The estimate is
        exact given no intervening acquisitions: it is the token deficit divided
        by the refill rate.
        """
        tokens = _validate_token_count("tokens", tokens)
        if tokens > self.capacity:
            raise ValueError(
                f"tokens ({tokens}) exceeds capacity ({self.capacity:g}); "
                "request can never be satisfied"
            )
        self._refill()
        deficit = tokens - self._tokens
        if deficit <= 0.0:
            return 0.0
        return deficit / self.refill_rate

    # -- acquisition ---------------------------------------------------------

    def try_acquire(self, tokens: int = 1) -> AcquireResult:
        """Attempt to spend ``tokens``; never raises.

        Refills first, then admits the request only if enough tokens are
        present, spending them if so. Returns an :class:`AcquireResult`
        describing the decision either way. A request larger than ``capacity``
        can never be admitted and is reported as rejected with the wait it would
        need if capacity were unbounded.
        """
        tokens = _validate_token_count("tokens", tokens)
        self._refill()

        if tokens <= self.capacity and self._tokens >= tokens:
            self._tokens -= tokens
            self._allowed_count += 1
            return AcquireResult(
                allowed=True,
                tokens=tokens,
                remaining=self._tokens,
                retry_after=0.0,
            )

        # Rejected: compute how long until the deficit would be refilled.
        deficit = tokens - self._tokens
        retry_after = deficit / self.refill_rate if deficit > 0.0 else 0.0
        self._rejected_count += 1
        return AcquireResult(
            allowed=False,
            tokens=tokens,
            remaining=self._tokens,
            retry_after=retry_after,
        )

    def acquire(self, tokens: int = 1) -> AcquireResult:
        """Spend ``tokens`` or raise :class:`RateLimitExceeded`.

        The raising counterpart to :meth:`try_acquire`. On failure nothing is
        spent and the exception carries the deterministic ``retry_after`` wait.
        Requests larger than ``capacity`` always raise, since no amount of
        waiting could satisfy them.
        """
        result = self.try_acquire(tokens)
        if not result.allowed:
            raise RateLimitExceeded(result.tokens, result.retry_after)
        return result

    # -- internals -----------------------------------------------------------

    def _now(self) -> float:
        now = self._clock()
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise TypeError("clock must return a real number")
        now = float(now)
        if math.isnan(now) or math.isinf(now):
            raise ValueError("clock must return a finite number")
        return now

    def _refill(self) -> None:
        """Accrue tokens for elapsed clock time and advance the refill marker.

        Guards against a non-monotonic clock: time that appears to move
        backwards accrues nothing and the marker is pinned forward so a later
        forward reading does not double-count the gap.
        """
        now = self._now()
        elapsed = now - self._last_refill
        if elapsed <= 0.0:
            # Clock did not advance (or went backwards); pin marker forward.
            self._last_refill = max(self._last_refill, now)
            return
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now
