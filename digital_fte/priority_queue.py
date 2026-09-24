"""Stable min/max priority queue for Digital FTE scheduling.

The reasoning loop pulls work in a deliberate order: some tasks are more urgent
than others, but tasks of equal urgency must be served in the order they
arrived so that no item is starved by a later arrival of the same priority.

This queue provides exactly that. It is backed by a binary heap, so push and
pop are O(log n), and it is made *stable* by carrying a monotonically
increasing insertion sequence in the heap key: ties on priority break on
sequence, which is arrival order. A single ``mode`` flag selects whether the
smallest (``"min"``) or largest (``"max"``) priority is served first; the
sequence tie-break stays arrival order in both modes. There is no clock and no
randomness -- ordering depends only on the priorities and the order of pushes.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass


def _validate_priority(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("priority must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError("priority must not be NaN")
    if math.isinf(number):
        raise ValueError("priority must be finite")
    return number


class PriorityQueueEmpty(Exception):
    """Raised when popping or peeking an empty :class:`PriorityQueue`."""


@dataclass(frozen=True)
class PrioritizedItem:
    """An item together with the priority and arrival sequence it was queued at."""

    item: object
    priority: float
    sequence: int


class PriorityQueue:
    """A stable priority queue served in min or max priority order.

    Args:
        mode: ``"min"`` to serve the smallest priority first (default) or
            ``"max"`` to serve the largest first. Equal priorities are always
            served in arrival order.

    Priorities may be any finite real number. The queue is not thread-safe by
    design; the loop drives it from a single thread.
    """

    def __init__(self, mode: str = "min") -> None:
        if mode not in ("min", "max"):
            raise ValueError("mode must be 'min' or 'max'")
        self.mode = mode
        self._heap: list[tuple[float, int, PrioritizedItem]] = []
        self._sequence = 0

    def __len__(self) -> int:
        return len(self._heap)

    @property
    def is_empty(self) -> bool:
        return not self._heap

    def push(self, item: object, priority: float) -> PrioritizedItem:
        """Add ``item`` at ``priority`` and return its :class:`PrioritizedItem`.

        The returned record carries the arrival ``sequence`` assigned to this
        push, which is what breaks priority ties.
        """
        priority = _validate_priority(priority)
        entry = PrioritizedItem(item=item, priority=priority, sequence=self._sequence)
        self._sequence += 1
        # For max-mode, negate priority so the heap (a min-heap) yields the
        # largest first. Sequence is never negated: ties always break on arrival.
        sort_priority = -priority if self.mode == "max" else priority
        heapq.heappush(self._heap, (sort_priority, entry.sequence, entry))
        return entry

    def peek(self) -> PrioritizedItem:
        """Return the next item to be served without removing it."""
        if not self._heap:
            raise PriorityQueueEmpty("priority queue is empty")
        return self._heap[0][2]

    def pop(self) -> PrioritizedItem:
        """Remove and return the next item (min or max priority, ties by arrival)."""
        if not self._heap:
            raise PriorityQueueEmpty("priority queue is empty")
        return heapq.heappop(self._heap)[2]

    def drain(self) -> tuple[PrioritizedItem, ...]:
        """Pop every entry, returned in the order they would be served."""
        drained: list[PrioritizedItem] = []
        while self._heap:
            drained.append(heapq.heappop(self._heap)[2])
        return tuple(drained)
