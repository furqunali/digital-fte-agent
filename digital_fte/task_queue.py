"""Priority task queue with stable ordering, dedupe and a capacity limit.

The Digital FTE intake stage can receive the same :class:`~digital_fte.models.Task`
more than once (a watcher re-firing on the same file, a retry, a duplicated
event). This queue gives the reasoning loop a deterministic pull order:

* higher ``priority`` values are served first;
* tasks sharing a priority keep first-in-first-out order (stable);
* a task whose ``task_id`` is already queued is treated as a duplicate;
* an optional ``capacity`` bounds how many tasks may wait at once.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

from .models import Task


class QueueFull(Exception):
    """Raised when pushing onto a queue that has reached its capacity."""


class QueueEmpty(Exception):
    """Raised when popping or peeking an empty queue."""


@dataclass(frozen=True)
class QueuedTask:
    """A task together with the priority and insertion order it was queued at."""

    task: Task
    priority: int
    sequence: int


class TaskQueue:
    """A bounded, de-duplicating priority queue of :class:`Task` values.

    Ordering is fully deterministic: entries are kept sorted by descending
    priority and, within the same priority, by ascending insertion sequence so
    that equal-priority tasks are served in the order they arrived.
    """

    def __init__(self, capacity: int | None = None) -> None:
        if capacity is not None and (
            not isinstance(capacity, int)
            or isinstance(capacity, bool)
            or capacity < 1
        ):
            raise ValueError("capacity must be a positive integer or None")
        self.capacity = capacity
        self._entries: list[QueuedTask] = []
        self._keys: list[tuple[int, int]] = []
        self._ids: set[str] = set()
        self._sequence = 0

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, task_id: object) -> bool:
        return task_id in self._ids

    @property
    def is_empty(self) -> bool:
        return not self._entries

    @property
    def is_full(self) -> bool:
        return self.capacity is not None and len(self._entries) >= self.capacity

    def task_ids(self) -> tuple[str, ...]:
        """Return the queued task ids in the order they would be popped."""
        return tuple(entry.task.task_id for entry in self._entries)

    def push(self, task: Task, priority: int = 0) -> bool:
        """Add ``task`` to the queue, returning ``True`` if it was accepted.

        A task whose ``task_id`` is already queued is a duplicate and is
        ignored (returns ``False``) without disturbing the existing ordering.
        Raises :class:`TypeError` for a bad argument type, :class:`ValueError`
        for an empty ``task_id`` and :class:`QueueFull` when at capacity.
        """
        if not isinstance(task, Task):
            raise TypeError("task must be a Task instance")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise TypeError("priority must be an integer")
        if not isinstance(task.task_id, str) or not task.task_id.strip():
            raise ValueError("task.task_id must be a non-empty string")
        if task.task_id in self._ids:
            return False
        if self.is_full:
            raise QueueFull(f"queue is at capacity ({self.capacity})")
        entry = QueuedTask(task=task, priority=priority, sequence=self._sequence)
        self._sequence += 1
        # Descending priority, ascending sequence -> negate priority for bisect.
        key = (-priority, entry.sequence)
        index = bisect.bisect_left(self._keys, key)
        self._keys.insert(index, key)
        self._entries.insert(index, entry)
        self._ids.add(task.task_id)
        return True

    def peek(self) -> Task:
        """Return the highest-priority task without removing it."""
        if not self._entries:
            raise QueueEmpty("queue is empty")
        return self._entries[0].task

    def pop(self) -> Task:
        """Remove and return the highest-priority task (stable within priority)."""
        if not self._entries:
            raise QueueEmpty("queue is empty")
        entry = self._entries.pop(0)
        self._keys.pop(0)
        self._ids.discard(entry.task.task_id)
        return entry.task

    def drain(self) -> tuple[Task, ...]:
        """Pop every task, returning them in the order they would be served."""
        drained = tuple(entry.task for entry in self._entries)
        self._entries.clear()
        self._keys.clear()
        self._ids.clear()
        return drained
