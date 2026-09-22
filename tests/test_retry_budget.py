import pytest

from digital_fte.retry_budget import (
    RetryBudget,
    RetryBudgetExceeded,
    RetryLedgerEntry,
)


def test_spend_charges_run_and_task_totals():
    budget = RetryBudget(total=5)
    assert budget.spend("a") == 1
    assert budget.spend("a") == 2
    assert budget.spend("b") == 1
    assert budget.spent == 3
    assert budget.remaining == 2
    assert budget.spent_for("a") == 2
    assert budget.spent_for("b") == 1


def test_total_cap_blocks_further_spend_across_tasks():
    budget = RetryBudget(total=2)
    budget.spend("a")
    budget.spend("b")
    assert budget.is_exhausted
    with pytest.raises(RetryBudgetExceeded, match="run retry budget"):
        budget.spend("c")
    # Nothing charged on the rejected spend.
    assert budget.spent == 2


def test_per_task_cap_blocks_before_total():
    budget = RetryBudget(total=10, per_task=2)
    budget.spend("hot")
    budget.spend("hot")
    with pytest.raises(RetryBudgetExceeded, match="per-task cap"):
        budget.spend("hot")
    # The run still has room; only this task is capped.
    assert budget.remaining == 8
    assert budget.spend("cool") == 1


def test_per_task_reported_before_total_when_both_reached():
    budget = RetryBudget(total=1, per_task=1)
    budget.spend("a")
    # 'a' hit its per-task cap AND the run is exhausted; per-task wins.
    with pytest.raises(RetryBudgetExceeded, match="per-task cap"):
        budget.spend("a")


def test_try_spend_returns_bool_and_never_overspends():
    budget = RetryBudget(total=2, per_task=1)
    assert budget.try_spend("a") is True
    # 'a' is per-task capped now.
    assert budget.try_spend("a") is False
    assert budget.try_spend("b") is True
    # Run is exhausted now.
    assert budget.try_spend("c") is False
    assert budget.spent == 2


def test_try_spend_charges_nothing_on_refusal():
    budget = RetryBudget(total=1)
    budget.try_spend("a")
    before = budget.spent
    assert budget.try_spend("b") is False
    assert budget.spent == before


def test_remaining_for_is_min_of_run_and_task_room():
    budget = RetryBudget(total=3, per_task=5)
    # Task cap (5) higher than run remaining (3) -> run wins.
    assert budget.remaining_for("a") == 3
    budget.spend("a")
    assert budget.remaining_for("a") == 2


def test_remaining_for_uses_task_cap_when_lower():
    budget = RetryBudget(total=10, per_task=2)
    assert budget.remaining_for("a") == 2
    budget.spend("a")
    assert budget.remaining_for("a") == 1
    budget.spend("a")
    assert budget.remaining_for("a") == 0
    assert budget.can_spend("a") is False


def test_remaining_for_without_per_task_is_run_remaining():
    budget = RetryBudget(total=4)
    assert budget.remaining_for("anything") == 4
    budget.spend("x")
    assert budget.remaining_for("anything") == 3


def test_can_spend_tracks_both_caps():
    budget = RetryBudget(total=1, per_task=1)
    assert budget.can_spend("a") is True
    budget.spend("a")
    assert budget.can_spend("a") is False
    assert budget.can_spend("b") is False  # run exhausted


def test_ledger_orders_by_spend_then_id():
    budget = RetryBudget(total=10, per_task=5)
    budget.spend("b")
    budget.spend("a")
    budget.spend("a")
    budget.spend("c")
    ledger = budget.ledger()
    assert ledger == (
        RetryLedgerEntry(task_id="a", spent=2, remaining=3),
        RetryLedgerEntry(task_id="b", spent=1, remaining=4),
        RetryLedgerEntry(task_id="c", spent=1, remaining=4),
    )


def test_ledger_remaining_none_without_per_task_cap():
    budget = RetryBudget(total=5)
    budget.spend("a")
    (entry,) = budget.ledger()
    assert entry == RetryLedgerEntry(task_id="a", spent=1, remaining=None)


def test_ledger_excludes_untouched_tasks():
    budget = RetryBudget(total=5)
    budget.spend("a")
    assert budget.spent_for("never") == 0
    assert [entry.task_id for entry in budget.ledger()] == ["a"]


def test_zero_total_budget_refuses_everything():
    budget = RetryBudget(total=0)
    assert budget.is_exhausted
    assert budget.can_spend("a") is False
    assert budget.try_spend("a") is False
    with pytest.raises(RetryBudgetExceeded):
        budget.spend("a")


def test_zero_per_task_cap_refuses_that_task():
    budget = RetryBudget(total=5, per_task=0)
    assert budget.remaining_for("a") == 0
    with pytest.raises(RetryBudgetExceeded, match="per-task cap"):
        budget.spend("a")


def test_invalid_total_rejected():
    for bad in (-1, True, 1.5, "3", None):
        with pytest.raises(ValueError):
            RetryBudget(total=bad)


def test_invalid_per_task_rejected():
    for bad in (-1, True, 1.5, "2"):
        with pytest.raises(ValueError):
            RetryBudget(total=5, per_task=bad)


def test_invalid_task_id_rejected():
    budget = RetryBudget(total=5)
    for bad in ("", "   ", 123, None):
        with pytest.raises(ValueError):
            budget.spend(bad)
        with pytest.raises(ValueError):
            budget.spent_for(bad)
        with pytest.raises(ValueError):
            budget.remaining_for(bad)
