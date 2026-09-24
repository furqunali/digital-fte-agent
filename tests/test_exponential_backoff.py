from dataclasses import FrozenInstanceError

import pytest

from digital_fte.exponential_backoff import (
    BackoffSchedule,
    backoff_delay,
    backoff_schedule,
)


# --- backoff_delay core -----------------------------------------------------

def test_first_attempt_is_base():
    assert backoff_delay(1, base=1.0, factor=2.0) == 1.0


def test_grows_by_factor():
    assert backoff_delay(2, base=1.0, factor=2.0) == 2.0
    assert backoff_delay(3, base=1.0, factor=2.0) == 4.0
    assert backoff_delay(4, base=1.0, factor=2.0) == 8.0


def test_max_delay_caps_growth():
    assert backoff_delay(10, base=1.0, factor=2.0, max_delay=5.0) == 5.0


def test_zero_base_is_all_zero():
    assert backoff_delay(5, base=0.0, factor=3.0) == 0.0


def test_factor_one_is_constant():
    assert backoff_delay(7, base=2.0, factor=1.0) == 2.0


# --- backoff_schedule -------------------------------------------------------

def test_schedule_length_and_values():
    assert backoff_schedule(4, base=1.0, factor=2.0) == (1.0, 2.0, 4.0, 8.0)


def test_schedule_respects_cap():
    assert backoff_schedule(4, base=1.0, factor=2.0, max_delay=3.0) == (1.0, 2.0, 3.0, 3.0)


def test_schedule_single_attempt():
    assert backoff_schedule(1, base=0.5, factor=2.0) == (0.5,)


# --- validation -------------------------------------------------------------

@pytest.mark.parametrize("bad", [0, -1])
def test_attempt_must_be_positive(bad):
    with pytest.raises(ValueError):
        backoff_delay(bad, base=1.0, factor=2.0)


@pytest.mark.parametrize("bad", [1.5, "1", True])
def test_attempt_must_be_int(bad):
    with pytest.raises(TypeError):
        backoff_delay(bad, base=1.0, factor=2.0)


def test_base_must_be_non_negative():
    with pytest.raises(ValueError):
        backoff_delay(1, base=-1.0, factor=2.0)


def test_factor_must_be_at_least_one():
    with pytest.raises(ValueError):
        backoff_delay(1, base=1.0, factor=0.5)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_base_rejected(bad):
    with pytest.raises(ValueError):
        backoff_delay(1, base=bad, factor=2.0)


def test_max_delay_must_be_positive():
    with pytest.raises(ValueError):
        backoff_delay(1, base=1.0, factor=2.0, max_delay=0.0)


def test_bool_base_rejected():
    with pytest.raises(TypeError):
        backoff_delay(1, base=True, factor=2.0)


# --- BackoffSchedule dataclass ---------------------------------------------

def test_dataclass_delay_before():
    sched = BackoffSchedule(base=1.0, factor=2.0, max_delay=5.0)
    assert sched.delay_before(3) == 4.0
    assert sched.delay_before(10) == 5.0


def test_dataclass_schedule_and_total():
    sched = BackoffSchedule(base=1.0, factor=2.0)
    assert sched.schedule(3) == (1.0, 2.0, 4.0)
    assert sched.total_delay(3) == pytest.approx(7.0)


def test_dataclass_is_frozen():
    sched = BackoffSchedule(base=1.0, factor=2.0)
    with pytest.raises(FrozenInstanceError):
        sched.base = 2.0  # type: ignore[misc]


def test_dataclass_validates_on_construction():
    with pytest.raises(ValueError):
        BackoffSchedule(base=-1.0, factor=2.0)
    with pytest.raises(ValueError):
        BackoffSchedule(base=1.0, factor=0.5)
