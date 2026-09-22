from dataclasses import FrozenInstanceError

import pytest

from digital_fte.retry_policy import (
    AttemptRecord,
    RetryExhausted,
    RetryOutcome,
    RetryPolicy,
)


class Boom(Exception):
    pass


class Other(Exception):
    pass


def make_flaky(fail_times, exc=Boom):
    """Return a zero-arg callable that raises ``exc`` the first N calls."""
    state = {"calls": 0}

    def call():
        state["calls"] += 1
        if state["calls"] <= fail_times:
            raise exc(f"fail {state['calls']}")
        return f"ok after {state['calls']}"

    call.state = state
    return call


# --- schedule / timing math -------------------------------------------------

def test_schedule_is_deterministic_exponential():
    policy = RetryPolicy(max_attempts=4, base_delay=1.0, factor=2.0)
    assert policy.schedule() == (0.0, 1.0, 2.0, 4.0)
    # Pure function of the fields: identical policy -> identical schedule.
    assert policy.schedule() == RetryPolicy(max_attempts=4, base_delay=1.0, factor=2.0).schedule()


def test_first_attempt_never_waits():
    assert RetryPolicy(base_delay=99.0).delay_before(1) == 0.0


def test_factor_one_gives_constant_delay():
    policy = RetryPolicy(max_attempts=5, base_delay=3.0, factor=1.0)
    assert policy.schedule() == (0.0, 3.0, 3.0, 3.0, 3.0)


def test_max_delay_caps_each_wait():
    policy = RetryPolicy(max_attempts=5, base_delay=1.0, factor=10.0, max_delay=25.0)
    assert policy.schedule() == (0.0, 1.0, 10.0, 25.0, 25.0)


def test_total_delay_sums_schedule():
    policy = RetryPolicy(max_attempts=4, base_delay=1.0, factor=2.0)
    assert policy.total_delay() == 7.0


def test_single_attempt_has_no_retry_delays():
    policy = RetryPolicy(max_attempts=1, base_delay=5.0)
    assert policy.schedule() == (0.0,)
    assert policy.total_delay() == 0.0


def test_delay_before_out_of_range_raises():
    policy = RetryPolicy(max_attempts=3)
    with pytest.raises(ValueError):
        policy.delay_before(0)
    with pytest.raises(ValueError):
        policy.delay_before(4)
    with pytest.raises(TypeError):
        policy.delay_before(True)
    with pytest.raises(TypeError):
        policy.delay_before(2.0)


# --- construction validation ------------------------------------------------

def test_invalid_max_attempts():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(TypeError):
        RetryPolicy(max_attempts=True)
    with pytest.raises(TypeError):
        RetryPolicy(max_attempts=2.0)


def test_invalid_base_delay_and_factor():
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=-1.0)
    with pytest.raises(ValueError):
        RetryPolicy(factor=0.5)  # factor must be >= 1
    with pytest.raises(TypeError):
        RetryPolicy(factor="2")


def test_invalid_max_delay():
    with pytest.raises(ValueError):
        RetryPolicy(max_delay=0.0)
    with pytest.raises(ValueError):
        RetryPolicy(max_delay=-3.0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=float("nan"))
    # None means unbounded and is valid.
    assert RetryPolicy(max_delay=None).max_delay is None


def test_policy_is_frozen():
    policy = RetryPolicy()
    with pytest.raises(FrozenInstanceError):
        policy.max_attempts = 9  # type: ignore[misc]


# --- execute: success paths -------------------------------------------------

def test_execute_success_first_try_no_sleep():
    waits = []
    policy = RetryPolicy(max_attempts=3, base_delay=1.0)
    outcome = policy.execute(lambda: "done", sleep=waits.append)
    assert isinstance(outcome, RetryOutcome)
    assert outcome.value == "done"
    assert outcome.attempts == 1
    assert outcome.failures == ()
    assert outcome.retried is False
    assert waits == []  # first attempt never sleeps


def test_execute_success_after_retries_records_failures_and_waits():
    waits = []
    policy = RetryPolicy(max_attempts=5, base_delay=1.0, factor=2.0)
    flaky = make_flaky(fail_times=2)
    outcome = policy.execute(flaky, retry_on=(Boom,), sleep=waits.append)
    assert outcome.value == "ok after 3"
    assert outcome.attempts == 3
    assert outcome.retried is True
    # Two failures recorded with the delays that preceded attempts 2 and 3.
    assert [f.attempt for f in outcome.failures] == [1, 2]
    assert all(isinstance(f, AttemptRecord) for f in outcome.failures)
    assert [f.delay for f in outcome.failures] == [0.0, 1.0]
    assert outcome.failures[0].error_type == "Boom"
    # sleep called only before the two retry attempts, in schedule order.
    assert waits == [1.0, 2.0]


# --- execute: failure paths -------------------------------------------------

def test_execute_exhausts_and_raises_with_last_exception():
    waits = []
    policy = RetryPolicy(max_attempts=3, base_delay=1.0, factor=2.0)
    flaky = make_flaky(fail_times=99)
    with pytest.raises(RetryExhausted) as info:
        policy.execute(flaky, retry_on=(Boom,), sleep=waits.append)
    err = info.value
    assert err.attempts == 3
    assert isinstance(err.last_exception, Boom)
    assert isinstance(err.__cause__, Boom)
    assert flaky.state["calls"] == 3
    assert waits == [1.0, 2.0]  # slept before attempts 2 and 3 only


def test_non_retriable_exception_propagates_immediately():
    waits = []
    policy = RetryPolicy(max_attempts=5, base_delay=1.0)

    def call():
        raise Other("nope")

    with pytest.raises(Other):
        policy.execute(call, retry_on=(Boom,), sleep=waits.append)
    assert waits == []  # failed on attempt 1, no further attempts scheduled


def test_retry_on_matches_subclasses():
    class SubBoom(Boom):
        pass

    policy = RetryPolicy(max_attempts=2, base_delay=0.0)
    flaky = make_flaky(fail_times=1, exc=SubBoom)
    outcome = policy.execute(flaky, retry_on=(Boom,), sleep=lambda _d: None)
    assert outcome.attempts == 2


def test_zero_base_delay_never_sleeps_but_still_retries():
    waits = []
    policy = RetryPolicy(max_attempts=3, base_delay=0.0, factor=2.0)
    flaky = make_flaky(fail_times=1)
    outcome = policy.execute(flaky, retry_on=(Boom,), sleep=waits.append)
    assert outcome.attempts == 2
    assert waits == []  # every scheduled delay is 0.0, so sleep is skipped


# --- execute: argument validation -------------------------------------------

def test_execute_rejects_bad_arguments():
    policy = RetryPolicy()
    with pytest.raises(TypeError):
        policy.execute("not callable")
    with pytest.raises(TypeError):
        policy.execute(lambda: 1, retry_on=())  # empty tuple
    with pytest.raises(TypeError):
        policy.execute(lambda: 1, retry_on=(int,))  # not an exception type
    with pytest.raises(TypeError):
        policy.execute(lambda: 1, sleep="nope")
