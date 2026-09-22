"""Dead-letter queue for tasks the reasoning loop has permanently abandoned.

When a task exhausts its retries (see :mod:`digital_fte.retry_budget`) or hits
an error the loop cannot recover from, it should not vanish silently -- it needs
to be parked somewhere durable, with the reason it failed, so an operator can
audit it and optionally requeue it later. :class:`DeadLetterQueue` is that park:

* :meth:`record` files a permanently-failed task with a human-readable reason,
  the number of attempts it took, and an optional caller-supplied timestamp;
* a task id may be dead-lettered only once -- a second attempt raises rather
  than silently overwriting the recorded reason;
* insertion order is preserved so a report reads oldest-failure-first, and
  :meth:`reason_counts` rolls the reasons up for the loop telemetry stage;
* :meth:`remove` pulls an entry back out (for a manual requeue) and
  :meth:`drain` empties the queue, both returning the removed record(s).

The queue holds task *ids* and metadata rather than whole ``Task`` objects so it
stays cheap to persist and never pins large payloads in memory.
"""
from __future__ import annotations

from dataclasses import dataclass


class DeadLetterError(Exception):
    """Base class for dead-letter queue errors."""


class AlreadyDeadLettered(DeadLetterError):
    """Raised when a task id is recorded that is already dead-lettered."""


class TaskNotDeadLettered(DeadLetterError):
    """Raised when a task id is looked up or removed but is not present."""


class DeadLetterQueueFull(DeadLetterError):
    """Raised when recording onto a queue that has reached its capacity."""


@dataclass(frozen=True)
class DeadLetter:
    """A permanently-failed task together with why and when it was parked."""

    task_id: str
    reason: str
    attempts: int
    failed_at: str | None
    sequence: int


@dataclass(frozen=True)
class ReasonCount:
    """How many dead-lettered tasks share a single failure reason."""

    reason: str
    count: int


class DeadLetterQueue:
    """A bounded, ordered store of permanently-failed tasks and their reasons.

    Records are keyed by ``task_id`` so a task can be dead-lettered at most once;
    iteration order is the order tasks were recorded, giving deterministic,
    oldest-first reports and reproducible telemetry roll-ups.
    """

    def __init__(self, capacity: int | None = None) -> None:
        if capacity is not None and (
            not isinstance(capacity, int)
            or isinstance(capacity, bool)
            or capacity < 1
        ):
            raise ValueError("capacity must be a positive integer or None")
        self.capacity = capacity
        self._entries: dict[str, DeadLetter] = {}
        self._sequence = 0

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, task_id: object) -> bool:
        return task_id in self._entries

    @property
    def is_empty(self) -> bool:
        """True when no task is currently dead-lettered."""
        return not self._entries

    @property
    def is_full(self) -> bool:
        """True when the queue has reached its configured capacity."""
        return self.capacity is not None and len(self._entries) >= self.capacity

    def record(
        self,
        task_id: str,
        reason: str,
        attempts: int = 1,
        failed_at: str | None = None,
    ) -> DeadLetter:
        """Park ``task_id`` as permanently failed and return its record.

        ``reason`` must be a non-empty, non-whitespace string; ``attempts`` is
        the (positive) number of tries the task took before being abandoned;
        ``failed_at`` is an optional caller-supplied timestamp string.

        Raises :class:`ValueError` for bad arguments, :class:`AlreadyDeadLettered`
        if the task id is already present (nothing is overwritten), and
        :class:`DeadLetterQueueFull` when the queue is at capacity.
        """
        self._validate_task_id(task_id)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            raise ValueError("attempts must be a positive integer")
        if failed_at is not None and (
            not isinstance(failed_at, str) or not failed_at.strip()
        ):
            raise ValueError("failed_at must be a non-empty string or None")
        if task_id in self._entries:
            raise AlreadyDeadLettered(f"task {task_id!r} is already dead-lettered")
        if self.is_full:
            raise DeadLetterQueueFull(
                f"dead-letter queue is at capacity ({self.capacity})"
            )
        entry = DeadLetter(
            task_id=task_id,
            reason=reason,
            attempts=attempts,
            failed_at=failed_at,
            sequence=self._sequence,
        )
        self._sequence += 1
        self._entries[task_id] = entry
        return entry

    def get(self, task_id: str) -> DeadLetter:
        """Return the record for ``task_id`` or raise if it is not present."""
        self._validate_task_id(task_id)
        try:
            return self._entries[task_id]
        except KeyError:
            raise TaskNotDeadLettered(
                f"task {task_id!r} is not dead-lettered"
            ) from None

    def task_ids(self) -> tuple[str, ...]:
        """Return the dead-lettered task ids in the order they were recorded."""
        return tuple(self._entries)

    def entries(self) -> tuple[DeadLetter, ...]:
        """Return every record in the order it was recorded (oldest first)."""
        return tuple(self._entries.values())

    def remove(self, task_id: str) -> DeadLetter:
        """Remove and return the record for ``task_id`` (e.g. to requeue it).

        Raises :class:`TaskNotDeadLettered` if the id is not present; the queue
        is otherwise unchanged.
        """
        self._validate_task_id(task_id)
        try:
            return self._entries.pop(task_id)
        except KeyError:
            raise TaskNotDeadLettered(
                f"task {task_id!r} is not dead-lettered"
            ) from None

    def reason_counts(self) -> tuple[ReasonCount, ...]:
        """Return reason -> count pairs, ordered by descending count then reason.

        This feeds the telemetry stage: the most common failure reason across a
        run surfaces first, with ties broken alphabetically for determinism.
        """
        counts: dict[str, int] = {}
        for entry in self._entries.values():
            counts[entry.reason] = counts.get(entry.reason, 0) + 1
        pairs = [ReasonCount(reason=reason, count=count) for reason, count in counts.items()]
        pairs.sort(key=lambda pair: (-pair.count, pair.reason))
        return tuple(pairs)

    def drain(self) -> tuple[DeadLetter, ...]:
        """Remove and return every record in recorded order, emptying the queue."""
        drained = tuple(self._entries.values())
        self._entries.clear()
        return drained

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
