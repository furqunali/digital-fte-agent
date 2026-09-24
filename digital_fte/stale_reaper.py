"""Identify tasks that have gone stale relative to a supplied ``now``.

Long-running work can stall: a task claims a resource and then stops making
progress. The reaper stage of the loop periodically looks for such tasks --
those whose last update is older than a maximum age -- so they can be requeued,
alerted on, or reaped. This module answers "which are stale?" as a pure function
of the tasks' last-update times, a caller-supplied ``now``, and a ``max_age``.
No clock is read here.

A task is stale when ``now - last_update > max_age`` (strictly older than the
threshold). Results are returned oldest-first so the most overdue task is dealt
with before the rest.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


def _validate_time(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    return number


def _validate_max_age(value: object) -> float:
    max_age = _validate_time("max_age", value)
    if max_age < 0.0:
        raise ValueError("max_age must be >= 0")
    return max_age


@dataclass(frozen=True)
class StaleItem:
    """A task judged stale, with its age at the moment of evaluation."""

    key: object
    last_update: float
    age: float


def _pairs(items: object):
    """Yield ``(key, last_update)`` pairs from a mapping or an iterable of pairs."""
    if isinstance(items, Mapping):
        yield from items.items()
        return
    if isinstance(items, Iterable) and not isinstance(items, (str, bytes)):
        for pair in items:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise TypeError("each item must be a (key, last_update) pair")
            yield pair[0], pair[1]
        return
    raise TypeError("items must be a mapping or an iterable of (key, last_update) pairs")


def find_stale(items: object, now: float, max_age: float) -> tuple[StaleItem, ...]:
    """Return the tasks in ``items`` that are stale at ``now``.

    Args:
        items: Either a mapping ``{key: last_update}`` or an iterable of
            ``(key, last_update)`` pairs. Each ``last_update`` must be a finite
            real number.
        now: The current time, in seconds, supplied by the caller.
        max_age: The maximum tolerated age; a task is stale when
            ``now - last_update > max_age``. Must be finite and ``>= 0``.

    Returns:
        A tuple of :class:`StaleItem`, sorted by descending age (oldest first);
        ties keep the input order (stable).

    Raises:
        TypeError: ``items`` is not a supported shape, or a time is not a real
            number.
        ValueError: a time is non-finite or ``max_age`` is negative.
    """
    now = _validate_time("now", now)
    max_age = _validate_max_age(max_age)

    stale: list[StaleItem] = []
    for key, last_update in _pairs(items):
        last_update = _validate_time("last_update", last_update)
        age = now - last_update
        if age > max_age:
            stale.append(StaleItem(key=key, last_update=last_update, age=age))

    # Stable sort by descending age: Python's sort is stable, so equal ages
    # keep their input order.
    stale.sort(key=lambda s: s.age, reverse=True)
    return tuple(stale)


def stale_keys(items: object, now: float, max_age: float) -> tuple[object, ...]:
    """Return just the keys of the stale tasks, oldest-first."""
    return tuple(item.key for item in find_stale(items, now, max_age))
