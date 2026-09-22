from dataclasses import FrozenInstanceError

import pytest

from digital_fte.circuit_breaker import (
    BreakerSnapshot,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class Boom(Exception):
    pass


class Unrelated(Exception):
    pass


class FakeClock:
    """A controllable monotonic clock for deterministic recovery timing."""

    def __init__(self, start=0.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def boom():
    raise Boom("dependency down")


def make_breaker(clock=None, **kwargs):
    kwargs.setdefault("failure_threshold", 3)
    kwargs.setdefault("recovery_timeout", 10.0)
    return CircuitBreaker(clock=clock or FakeClock(), **kwargs)


# --- construction validation ------------------------------------------------

def test_defaults_start_closed():
    breaker = CircuitBreaker()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allows_call() is True
    assert breaker.consecutive_failures == 0


def test_invalid_failure_threshold():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(TypeError):
        CircuitBreaker(failure_threshold=True)
    with pytest.raises(TypeError):
        CircuitBreaker(failure_threshold=2.0)


def test_invalid_recovery_timeout():
    with pytest.raises(ValueError):
        CircuitBreaker(recovery_timeout=0.0)
    with pytest.raises(ValueError):
        CircuitBreaker(recovery_timeout=-1.0)
    with pytest.raises(ValueError):
        CircuitBreaker(recovery_timeout=float("nan"))
    with pytest.raises(TypeError):
        CircuitBreaker(recovery_timeout="5")


def test_invalid_success_threshold_and_record_on_and_clock():
    with pytest.raises(ValueError):
        CircuitBreaker(success_threshold=0)
    with pytest.raises(TypeError):
        CircuitBreaker(record_on=())
    with pytest.raises(TypeError):
        CircuitBreaker(record_on=(int,))  # not an exception type
    with pytest.raises(TypeError):
        CircuitBreaker(clock="nope")


# --- CLOSED behaviour -------------------------------------------------------

def test_success_passes_through_and_returns_value():
    breaker = make_breaker()
    assert breaker.call(lambda: 42) == 42
    assert breaker.state is CircuitState.CLOSED
    assert breaker.snapshot().total_calls == 1


def test_success_resets_partial_failure_streak():
    breaker = make_breaker(failure_threshold=3)
    with pytest.raises(Boom):
        breaker.call(boom)
    with pytest.raises(Boom):
        breaker.call(boom)
    assert breaker.consecutive_failures == 2
    breaker.call(lambda: "ok")  # one success clears the streak
    assert breaker.consecutive_failures == 0
    assert breaker.state is CircuitState.CLOSED


def test_trips_open_after_threshold_consecutive_failures():
    breaker = make_breaker(failure_threshold=3)
    for _ in range(3):
        with pytest.raises(Boom):
            breaker.call(boom)
    assert breaker.state is CircuitState.OPEN
    assert breaker.snapshot().opened_count == 1


def test_unrecorded_exception_propagates_without_tripping():
    breaker = make_breaker(failure_threshold=1, record_on=(Boom,))

    def raise_unrelated():
        raise Unrelated("bug, not a dependency failure")

    with pytest.raises(Unrelated):
        breaker.call(raise_unrelated)
    # State untouched and the call is invisible to telemetry.
    assert breaker.state is CircuitState.CLOSED
    assert breaker.consecutive_failures == 0
    snap = breaker.snapshot()
    assert snap.total_calls == 0
    assert snap.total_failures == 0


# --- OPEN behaviour ---------------------------------------------------------

def test_open_rejects_calls_fast_without_invoking_func():
    clock = FakeClock()
    breaker = make_breaker(clock=clock, failure_threshold=1)
    with pytest.raises(Boom):
        breaker.call(boom)
    assert breaker.state is CircuitState.OPEN

    called = {"n": 0}

    def guarded():
        called["n"] += 1
        return "should not run"

    with pytest.raises(CircuitOpenError) as info:
        breaker.call(guarded)
    assert called["n"] == 0  # func never invoked while open
    assert info.value.retry_after == pytest.approx(10.0)
    assert breaker.snapshot().total_rejections == 1


def test_time_until_retry_counts_down_then_none_when_closed():
    clock = FakeClock()
    breaker = make_breaker(clock=clock, failure_threshold=1, recovery_timeout=10.0)
    with pytest.raises(Boom):
        breaker.call(boom)
    assert breaker.time_until_retry() == pytest.approx(10.0)
    clock.advance(4.0)
    assert breaker.time_until_retry() == pytest.approx(6.0)
    # Fully elapsed clamps at 0.0 (not negative) before the lazy transition.
    clock.advance(20.0)
    assert breaker.time_until_retry() == pytest.approx(0.0)


# --- OPEN -> HALF_OPEN recovery ---------------------------------------------

def test_recovers_to_half_open_after_timeout():
    clock = FakeClock()
    breaker = make_breaker(clock=clock, failure_threshold=1, recovery_timeout=10.0)
    with pytest.raises(Boom):
        breaker.call(boom)
    assert breaker.state is CircuitState.OPEN
    clock.advance(9.9)
    assert breaker.state is CircuitState.OPEN  # not yet
    clock.advance(0.1)
    assert breaker.state is CircuitState.HALF_OPEN
    assert breaker.time_until_retry() is None


def test_half_open_success_closes_after_success_threshold():
    clock = FakeClock()
    breaker = make_breaker(
        clock=clock, failure_threshold=1, recovery_timeout=5.0, success_threshold=2
    )
    with pytest.raises(Boom):
        breaker.call(boom)
    clock.advance(5.0)
    assert breaker.state is CircuitState.HALF_OPEN
    breaker.call(lambda: "probe-1")
    assert breaker.state is CircuitState.HALF_OPEN  # one more needed
    breaker.call(lambda: "probe-2")
    assert breaker.state is CircuitState.CLOSED
    assert breaker.consecutive_failures == 0


def test_half_open_failure_reopens_and_restarts_cooldown():
    clock = FakeClock()
    breaker = make_breaker(clock=clock, failure_threshold=1, recovery_timeout=5.0)
    with pytest.raises(Boom):
        breaker.call(boom)
    clock.advance(5.0)
    assert breaker.state is CircuitState.HALF_OPEN
    with pytest.raises(Boom):
        breaker.call(boom)  # probe fails
    assert breaker.state is CircuitState.OPEN
    assert breaker.snapshot().opened_count == 2
    # Cooldown restarted from the probe-failure moment.
    assert breaker.time_until_retry() == pytest.approx(5.0)


def test_half_open_limits_concurrent_probe_slots():
    clock = FakeClock()
    breaker = make_breaker(
        clock=clock, failure_threshold=1, recovery_timeout=5.0, success_threshold=1
    )
    with pytest.raises(Boom):
        breaker.call(boom)
    clock.advance(5.0)
    assert breaker.state is CircuitState.HALF_OPEN

    # Re-enter the breaker from inside a probe: the nested call must be rejected
    # because the single probe slot is already taken.
    outcomes = {}

    def reentrant_probe():
        outcomes["nested_allowed"] = breaker.allows_call()
        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: "nested")
        return "outer"

    assert breaker.call(reentrant_probe) == "outer"
    assert outcomes["nested_allowed"] is False
    # The successful outer probe still closed the breaker afterwards.
    assert breaker.state is CircuitState.CLOSED


# --- manual record_* API ----------------------------------------------------

def test_manual_record_failure_trips_like_call():
    breaker = make_breaker(failure_threshold=2)
    breaker.record_failure()
    assert breaker.state is CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN


def test_manual_record_success_clears_streak():
    breaker = make_breaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker.consecutive_failures == 0


# --- reset ------------------------------------------------------------------

def test_reset_returns_to_closed_but_keeps_cumulative_counters():
    breaker = make_breaker(failure_threshold=1)
    with pytest.raises(Boom):
        breaker.call(boom)
    assert breaker.state is CircuitState.OPEN
    breaker.reset()
    assert breaker.state is CircuitState.CLOSED
    assert breaker.allows_call() is True
    snap = breaker.snapshot()
    assert snap.opened_count == 1  # history preserved
    assert snap.total_failures == 1


# --- snapshot ---------------------------------------------------------------

def test_snapshot_is_immutable_and_reports_state():
    clock = FakeClock()
    breaker = make_breaker(clock=clock, failure_threshold=1, recovery_timeout=3.0)
    with pytest.raises(Boom):
        breaker.call(boom)
    snap = breaker.snapshot()
    assert isinstance(snap, BreakerSnapshot)
    assert snap.state is CircuitState.OPEN
    assert snap.total_calls == 1
    assert snap.total_failures == 1
    assert snap.time_until_retry == pytest.approx(3.0)
    with pytest.raises(FrozenInstanceError):
        snap.state = CircuitState.CLOSED  # frozen dataclass


def test_state_enum_equals_wire_value():
    assert CircuitState.OPEN == "open"
    assert CircuitState.CLOSED == "closed"
    assert CircuitState.HALF_OPEN == "half_open"


def test_call_rejects_non_callable():
    breaker = make_breaker()
    with pytest.raises(TypeError):
        breaker.call("not callable")
