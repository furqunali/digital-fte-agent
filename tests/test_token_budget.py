import pytest

from digital_fte.token_budget import BudgetExceeded, BudgetSnapshot, TokenBudget


# --- construction / validation ---------------------------------------------

def test_starts_full():
    b = TokenBudget(1000)
    assert b.remaining() == 1000
    assert b.usable == 1000


def test_safety_reserve_reduces_usable():
    b = TokenBudget(1000, safety_reserve=100)
    assert b.usable == 900
    assert b.remaining() == 900


def test_safety_reserve_cannot_exceed_total():
    with pytest.raises(ValueError):
        TokenBudget(100, safety_reserve=200)


def test_negative_total_rejected():
    with pytest.raises(ValueError):
        TokenBudget(-1)


def test_bool_total_rejected():
    with pytest.raises(TypeError):
        TokenBudget(True)


def test_float_total_rejected():
    with pytest.raises(TypeError):
        TokenBudget(100.0)


# --- reserve / release ------------------------------------------------------

def test_reserve_reduces_remaining():
    b = TokenBudget(1000)
    assert b.reserve(300) == 700
    assert b.reserved == 300


def test_reserve_over_budget_raises():
    b = TokenBudget(100)
    with pytest.raises(BudgetExceeded) as exc:
        b.reserve(101)
    assert exc.value.requested == 101
    assert exc.value.available == 100


def test_release_restores_remaining():
    b = TokenBudget(1000)
    b.reserve(300)
    assert b.release(300) == 1000
    assert b.reserved == 0


def test_release_more_than_reserved_raises():
    b = TokenBudget(1000)
    b.reserve(100)
    with pytest.raises(ValueError):
        b.release(200)


# --- consume ----------------------------------------------------------------

def test_consume_reduces_remaining():
    b = TokenBudget(1000)
    assert b.consume(400) == 600
    assert b.consumed == 400


def test_consume_over_budget_raises():
    b = TokenBudget(100)
    with pytest.raises(BudgetExceeded):
        b.consume(101)


def test_consume_respects_safety_reserve():
    b = TokenBudget(100, safety_reserve=30)
    b.consume(70)
    assert b.remaining() == 0
    with pytest.raises(BudgetExceeded):
        b.consume(1)


# --- commit -----------------------------------------------------------------

def test_commit_less_than_reserved_frees_difference():
    b = TokenBudget(1000)
    b.reserve(300)
    # Actual usage was only 200; 100 returns to the pool.
    assert b.commit(300, 200) == 800
    assert b.reserved == 0
    assert b.consumed == 200


def test_commit_more_than_reserved_allowed_if_fits():
    b = TokenBudget(1000)
    b.reserve(200)
    assert b.commit(200, 250) == 750
    assert b.consumed == 250


def test_commit_over_budget_leaves_state_unchanged():
    b = TokenBudget(300)
    b.reserve(100)
    b.consume(150)  # remaining now 50, reserved 100
    with pytest.raises(BudgetExceeded):
        # release 100 -> available becomes 150; asking 200 exceeds it.
        b.commit(100, 200)
    # unchanged
    assert b.reserved == 100
    assert b.consumed == 150


def test_commit_release_more_than_reserved_raises():
    b = TokenBudget(1000)
    b.reserve(50)
    with pytest.raises(ValueError):
        b.commit(100, 10)


# --- snapshot ---------------------------------------------------------------

def test_snapshot_reports_counters():
    b = TokenBudget(1000, safety_reserve=100)
    b.reserve(200)
    b.consume(300)
    snap = b.snapshot()
    assert isinstance(snap, BudgetSnapshot)
    assert snap.total == 1000
    assert snap.safety_reserve == 100
    assert snap.reserved == 200
    assert snap.consumed == 300
    assert snap.remaining == 400  # 900 usable - 200 - 300


# --- negative amounts -------------------------------------------------------

def test_negative_reserve_rejected():
    b = TokenBudget(1000)
    with pytest.raises(ValueError):
        b.reserve(-1)
