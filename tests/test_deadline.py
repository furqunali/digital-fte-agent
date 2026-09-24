from dataclasses import FrozenInstanceError

import pytest

from digital_fte.deadline import Deadline


# --- construction / validation ---------------------------------------------

def test_deadline_property():
    d = Deadline(start=100.0, budget=30.0)
    assert d.deadline == 130.0


def test_budget_must_be_positive():
    with pytest.raises(ValueError):
        Deadline(start=0.0, budget=0.0)
    with pytest.raises(ValueError):
        Deadline(start=0.0, budget=-5.0)


def test_bool_start_rejected():
    with pytest.raises(TypeError):
        Deadline(start=True, budget=10.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_rejected(bad):
    with pytest.raises(ValueError):
        Deadline(start=bad, budget=10.0)


def test_is_frozen():
    d = Deadline(start=0.0, budget=10.0)
    with pytest.raises(FrozenInstanceError):
        d.budget = 20.0  # type: ignore[misc]


# --- remaining --------------------------------------------------------------

def test_remaining_before_expiry():
    d = Deadline(start=0.0, budget=10.0)
    assert d.remaining(now=3.0) == 7.0


def test_remaining_clamped_at_zero():
    d = Deadline(start=0.0, budget=10.0)
    assert d.remaining(now=15.0) == 0.0


def test_remaining_at_start():
    d = Deadline(start=5.0, budget=10.0)
    assert d.remaining(now=5.0) == 10.0


# --- expired ----------------------------------------------------------------

def test_not_expired_before_deadline():
    d = Deadline(start=0.0, budget=10.0)
    assert d.expired(now=9.999) is False


def test_expired_exactly_at_deadline():
    d = Deadline(start=0.0, budget=10.0)
    assert d.expired(now=10.0) is True


def test_expired_after_deadline():
    d = Deadline(start=0.0, budget=10.0)
    assert d.expired(now=11.0) is True


# --- overrun / elapsed / fraction -------------------------------------------

def test_overrun_zero_before_expiry():
    d = Deadline(start=0.0, budget=10.0)
    assert d.overrun(now=5.0) == 0.0


def test_overrun_positive_after_expiry():
    d = Deadline(start=0.0, budget=10.0)
    assert d.overrun(now=13.0) == 3.0


def test_elapsed_clamped_before_start():
    d = Deadline(start=10.0, budget=5.0)
    assert d.elapsed(now=8.0) == 0.0


def test_elapsed_counts_from_start():
    d = Deadline(start=10.0, budget=5.0)
    assert d.elapsed(now=12.0) == 2.0


def test_fraction_elapsed_midway():
    d = Deadline(start=0.0, budget=10.0)
    assert d.fraction_elapsed(now=5.0) == 0.5


def test_fraction_elapsed_capped_at_one():
    d = Deadline(start=0.0, budget=10.0)
    assert d.fraction_elapsed(now=100.0) == 1.0


def test_now_validated():
    d = Deadline(start=0.0, budget=10.0)
    with pytest.raises(ValueError):
        d.remaining(now=float("nan"))
    with pytest.raises(TypeError):
        d.remaining(now=True)
