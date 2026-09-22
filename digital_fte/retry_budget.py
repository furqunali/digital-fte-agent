"""Run-scoped retry budget that caps total retries across a Digital FTE run.

A single reasoning loop may retry a failing step several times, and a run may
drive many tasks. Without a shared ceiling a run can spin forever burning
retries on a handful of pathological tasks. :class:`RetryBudget` gives the
run one global budget of retry attempts and, optionally, a per-task cap:

* ``total`` bounds how many retries the whole run may spend;
* ``per_task`` (optional) bounds how many of those any single task may spend;
* :meth:`try_spend` atomically checks both caps and, only if both allow it,
  charges one retry -- so a caller never over-spends the budget.

The tracker keeps a per-task ledger so a run can report exactly where its
retries went, which feeds the loop telemetry stage.
"""
from __future__ import annotations

from dataclasses import dataclass


class RetryBudgetExceeded(Exception):
    """Raised when :meth:`RetryBudget.spend` is charged past a cap."""


@dataclass(frozen=True)
class RetryLedgerEntry:
    """How many retries a single task spent and its remaining per-task room."""

    task_id: str
    spent: int
    remaining: int | None


class RetryBudget:
    """A run-scoped counter of retry attempts with an optional per-task cap.

    Ordering of checks is deterministic: a spend is refused if *either* the
    per-task cap or the total cap is already reached, and the per-task cap is
    reported first so callers see the most specific reason. Nothing is charged
    unless the spend succeeds, so the budget can never be driven negative.
    """

    def __init__(self, total: int, per_task: int | None = None) -> None:
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise ValueError("total must be a non-negative integer")
        if per_task is not None and (
            not isinstance(per_task, int)
            or isinstance(per_task, bool)
            or per_task < 0
        ):
            raise ValueError("per_task must be a non-negative integer or None")
        self.total = total
        self.per_task = per_task
        self._spent = 0
        self._per_task_spent: dict[str, int] = {}

    @property
    def spent(self) -> int:
        """Total retries charged against the run so far."""
        return self._spent

    @property
    def remaining(self) -> int:
        """Retries still available to the run as a whole."""
        return self.total - self._spent

    @property
    def is_exhausted(self) -> bool:
        """True when the run-wide budget can accept no further retries."""
        return self._spent >= self.total

    def spent_for(self, task_id: str) -> int:
        """Return how many retries ``task_id`` has been charged."""
        self._validate_task_id(task_id)
        return self._per_task_spent.get(task_id, 0)

    def remaining_for(self, task_id: str) -> int:
        """Return retries left for ``task_id``, honouring both caps.

        The effective room is the smaller of the run-wide remaining and, when
        set, the per-task remaining -- a task can never spend more than the run
        has left even if its own cap is higher.
        """
        self._validate_task_id(task_id)
        run_room = self.remaining
        if self.per_task is None:
            return run_room
        task_room = self.per_task - self._per_task_spent.get(task_id, 0)
        return min(run_room, task_room)

    def can_spend(self, task_id: str) -> bool:
        """Return whether a single retry could be charged to ``task_id`` now."""
        return self.remaining_for(task_id) > 0

    def try_spend(self, task_id: str) -> bool:
        """Charge one retry to ``task_id`` if allowed, returning success.

        This is the non-raising counterpart to :meth:`spend`: it returns
        ``False`` (and charges nothing) when either cap is reached, so it can be
        used directly as a loop guard.
        """
        if not self.can_spend(task_id):
            return False
        self._charge(task_id)
        return True

    def spend(self, task_id: str) -> int:
        """Charge one retry to ``task_id`` and return its new per-task total.

        Raises :class:`RetryBudgetExceeded` when the per-task cap (reported
        first) or the run-wide budget is already exhausted; nothing is charged
        in that case.
        """
        self._validate_task_id(task_id)
        if self.per_task is not None and (
            self._per_task_spent.get(task_id, 0) >= self.per_task
        ):
            raise RetryBudgetExceeded(
                f"task {task_id!r} reached its per-task cap ({self.per_task})"
            )
        if self.is_exhausted:
            raise RetryBudgetExceeded(
                f"run retry budget exhausted ({self.total})"
            )
        return self._charge(task_id)

    def ledger(self) -> tuple[RetryLedgerEntry, ...]:
        """Return per-task retry usage, ordered by descending spend then id.

        Only tasks that actually spent a retry appear. ``remaining`` is ``None``
        when no per-task cap is configured.
        """
        entries = [
            RetryLedgerEntry(
                task_id=task_id,
                spent=spent,
                remaining=None if self.per_task is None else self.per_task - spent,
            )
            for task_id, spent in self._per_task_spent.items()
        ]
        entries.sort(key=lambda entry: (-entry.spent, entry.task_id))
        return tuple(entries)

    def _charge(self, task_id: str) -> int:
        new_total = self._per_task_spent.get(task_id, 0) + 1
        self._per_task_spent[task_id] = new_total
        self._spent += 1
        return new_total

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
