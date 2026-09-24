from dataclasses import FrozenInstanceError

import pytest

from digital_fte.rate_limiter import (
    AcquireResult,
    RateLimitExceeded,
    TokenBucket,
)


class FakeClock:
    """A manually advanced monotonic clock for deterministic refill tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


# --- construction / validation ---------------------------------------------

def test_defaults_to_full_bucket():
    bucket = TokenBucket(capacity=5, refill_rate=1.0, clock=FakeClock())
    assert bucket.available_tokens() == 5.0


def test_initial_tokens_can_start_empty():
    bucket = TokenBucket(capacity=5, refill_rate=1.0, initial_tokens=0, clock=FakeClock())
    assert bucket.available_tokens() == 0.0


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_capacity_must_be_positive_finite(bad):
    with pytest.raises(ValueError):
        TokenBucket(capacity=bad, refill_rate=1.0)


@pytest.mark.parametrize("bad", [0, -0.5, float("nan"), float("inf")])
def test_refill_rate_must_be_positive_finite(bad):
    with pytest.raises(ValueError):
        TokenBucket(capacity=5, refill_rate=bad)


def test_boolean_capacity_rejected():
    # bool is a subclass of int; must be rejected explicitly.
    with pytest.raises(TypeError):
        TokenBucket(capacity=True, refill_rate=1.0)


def test_initial_tokens_out_of_range_rejected():
    with pytest.raises(ValueError):
        TokenBucket(capacity=5, refill_rate=1.0, initial_tokens=6)
    with pytest.raises(ValueError):
        TokenBucket(capacity=5, refill_rate=1.0, initial_tokens=-1)


def test_non_callable_clock_rejected():
    with pytest.raises(TypeError):
        TokenBucket(capacity=5, refill_rate=1.0, clock=123)


# --- basic acquisition ------------------------------------------------------

def test_try_acquire_spends_tokens():
    bucket = TokenBucket(capacity=3, refill_rate=1.0, clock=FakeClock())
    result = bucket.try_acquire()
    assert isinstance(result, AcquireResult)
    assert result.allowed is True
    assert result.tokens == 1
    assert result.remaining == 2.0
    assert result.retry_after == 0.0
    assert bucket.allowed_count == 1


def test_burst_up_to_capacity_then_reject():
    clock = FakeClock()
    bucket = TokenBucket(capacity=3, refill_rate=1.0, clock=clock)
    assert bucket.try_acquire().allowed
    assert bucket.try_acquire().allowed
    assert bucket.try_acquire().allowed
    rejected = bucket.try_acquire()
    assert rejected.allowed is False
    assert rejected.remaining == 0.0
    # One token refills in 1s at 1 token/s.
    assert rejected.retry_after == pytest.approx(1.0)
    assert bucket.allowed_count == 3
    assert bucket.rejected_count == 1


def test_multi_token_acquire():
    bucket = TokenBucket(capacity=10, refill_rate=1.0, clock=FakeClock())
    result = bucket.try_acquire(4)
    assert result.allowed
    assert result.remaining == 6.0


def test_acquire_raises_when_empty():
    bucket = TokenBucket(capacity=1, refill_rate=2.0, initial_tokens=0, clock=FakeClock())
    with pytest.raises(RateLimitExceeded) as exc:
        bucket.acquire()
    # Deficit of 1 token at 2 tokens/s -> 0.5s.
    assert exc.value.retry_after == pytest.approx(0.5)
    assert exc.value.tokens == 1


def test_acquire_returns_result_on_success():
    bucket = TokenBucket(capacity=2, refill_rate=1.0, clock=FakeClock())
    result = bucket.acquire(2)
    assert result.allowed
    assert result.remaining == 0.0


# --- refill over time -------------------------------------------------------

def test_refill_accrues_with_clock():
    clock = FakeClock()
    bucket = TokenBucket(capacity=5, refill_rate=2.0, initial_tokens=0, clock=clock)
    clock.advance(1.0)  # 2 tokens/s * 1s = 2 tokens
    assert bucket.available_tokens() == pytest.approx(2.0)
    assert bucket.try_acquire(2).allowed


def test_refill_never_exceeds_capacity():
    clock = FakeClock()
    bucket = TokenBucket(capacity=5, refill_rate=10.0, initial_tokens=0, clock=clock)
    clock.advance(100.0)  # would be 1000 tokens; clamped to capacity
    assert bucket.available_tokens() == 5.0


def test_partial_refill_is_fractional():
    clock = FakeClock()
    bucket = TokenBucket(capacity=10, refill_rate=1.0, initial_tokens=0, clock=clock)
    clock.advance(0.5)
    assert bucket.available_tokens() == pytest.approx(0.5)
    # Not enough for a whole token yet.
    assert bucket.try_acquire(1).allowed is False


def test_reject_then_refill_then_allow():
    clock = FakeClock()
    bucket = TokenBucket(capacity=1, refill_rate=1.0, clock=clock)
    assert bucket.acquire().allowed
    assert bucket.try_acquire().allowed is False
    clock.advance(1.0)
    assert bucket.acquire().allowed


# --- sustained rate ---------------------------------------------------------

def test_long_run_rate_bounded_by_refill():
    clock = FakeClock()
    bucket = TokenBucket(capacity=1, refill_rate=1.0, initial_tokens=1, clock=clock)
    admitted = 0
    # Simulate 10 seconds, offering a request every 0.25s.
    for _ in range(40):
        if bucket.try_acquire().allowed:
            admitted += 1
        clock.advance(0.25)
    # Start full (1) + ~10 tokens over 10s -> ~11 admitted, never far above rate.
    assert 10 <= admitted <= 12


# --- time_until_available ---------------------------------------------------

def test_time_until_available_zero_when_ready():
    bucket = TokenBucket(capacity=5, refill_rate=1.0, clock=FakeClock())
    assert bucket.time_until_available(3) == 0.0


def test_time_until_available_computes_deficit():
    clock = FakeClock()
    bucket = TokenBucket(capacity=5, refill_rate=2.0, initial_tokens=1, clock=clock)
    # Need 5, have 1, deficit 4, at 2/s -> 2.0s.
    assert bucket.time_until_available(5) == pytest.approx(2.0)


def test_time_until_available_does_not_spend():
    bucket = TokenBucket(capacity=5, refill_rate=1.0, clock=FakeClock())
    bucket.time_until_available(2)
    assert bucket.available_tokens() == 5.0


# --- oversized requests -----------------------------------------------------

def test_request_larger_than_capacity_never_admitted():
    bucket = TokenBucket(capacity=3, refill_rate=1.0, clock=FakeClock())
    result = bucket.try_acquire(4)
    assert result.allowed is False
    assert bucket.rejected_count == 1


def test_oversized_acquire_raises():
    bucket = TokenBucket(capacity=3, refill_rate=1.0, clock=FakeClock())
    with pytest.raises(RateLimitExceeded):
        bucket.acquire(4)


def test_oversized_time_until_available_raises():
    bucket = TokenBucket(capacity=3, refill_rate=1.0, clock=FakeClock())
    with pytest.raises(ValueError):
        bucket.time_until_available(4)


# --- token-count validation -------------------------------------------------

@pytest.mark.parametrize("bad", [0, -1])
def test_acquire_rejects_non_positive_tokens(bad):
    bucket = TokenBucket(capacity=5, refill_rate=1.0, clock=FakeClock())
    with pytest.raises(ValueError):
        bucket.try_acquire(bad)


@pytest.mark.parametrize("bad", [1.5, "1", True])
def test_acquire_rejects_non_integer_tokens(bad):
    bucket = TokenBucket(capacity=5, refill_rate=1.0, clock=FakeClock())
    with pytest.raises(TypeError):
        bucket.try_acquire(bad)


# --- clock robustness -------------------------------------------------------

def test_backwards_clock_does_not_accrue():
    clock = FakeClock(start=100.0)
    bucket = TokenBucket(capacity=5, refill_rate=1.0, initial_tokens=0, clock=clock)
    clock.t = 50.0  # clock jumps backwards
    assert bucket.available_tokens() == 0.0
    # And a later forward move past the original does not double-count.
    clock.t = 101.0
    assert bucket.available_tokens() == pytest.approx(1.0)


def test_result_is_frozen():
    result = AcquireResult(allowed=True, tokens=1, remaining=0.0, retry_after=0.0)
    with pytest.raises(FrozenInstanceError):
        result.allowed = False  # type: ignore[misc]
