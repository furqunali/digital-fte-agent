from dataclasses import FrozenInstanceError

import pytest

from digital_fte.timeout_guard import OK, TIMED_OUT, TimeoutStatus, classify_timeout


# --- ok path ----------------------------------------------------------------

def test_within_budget_is_ok():
    status = classify_timeout(elapsed=3.0, budget=10.0)
    assert status.state == OK
    assert status.ok is True
    assert status.timed_out is False


def test_within_budget_remaining():
    status = classify_timeout(elapsed=3.0, budget=10.0)
    assert status.remaining == 7.0
    assert status.overrun == 0.0


def test_zero_elapsed_full_remaining():
    status = classify_timeout(elapsed=0.0, budget=10.0)
    assert status.remaining == 10.0
    assert status.ok


# --- timed-out path ---------------------------------------------------------

def test_exactly_at_budget_times_out():
    status = classify_timeout(elapsed=10.0, budget=10.0)
    assert status.state == TIMED_OUT
    assert status.timed_out is True
    assert status.remaining == 0.0
    assert status.overrun == 0.0


def test_over_budget_times_out():
    status = classify_timeout(elapsed=13.0, budget=10.0)
    assert status.timed_out
    assert status.overrun == 3.0
    assert status.remaining == 0.0


# --- record shape -----------------------------------------------------------

def test_returns_timeout_status():
    status = classify_timeout(elapsed=1.0, budget=2.0)
    assert isinstance(status, TimeoutStatus)
    assert status.elapsed == 1.0
    assert status.budget == 2.0


def test_is_frozen():
    status = classify_timeout(elapsed=1.0, budget=2.0)
    with pytest.raises(FrozenInstanceError):
        status.state = OK  # type: ignore[misc]


# --- validation -------------------------------------------------------------

def test_negative_elapsed_rejected():
    with pytest.raises(ValueError):
        classify_timeout(elapsed=-1.0, budget=10.0)


def test_zero_budget_rejected():
    with pytest.raises(ValueError):
        classify_timeout(elapsed=1.0, budget=0.0)


def test_negative_budget_rejected():
    with pytest.raises(ValueError):
        classify_timeout(elapsed=1.0, budget=-5.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_elapsed_rejected(bad):
    with pytest.raises(ValueError):
        classify_timeout(elapsed=bad, budget=10.0)


def test_bool_elapsed_rejected():
    with pytest.raises(TypeError):
        classify_timeout(elapsed=True, budget=10.0)


def test_string_budget_rejected():
    with pytest.raises(TypeError):
        classify_timeout(elapsed=1.0, budget="10")
