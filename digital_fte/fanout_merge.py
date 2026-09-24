"""De-duplicating merge of fan-out results for a Digital FTE run.

A fan-out step dispatches the same query to several workers (shards, replicas,
retries) and collects a list of results from each. The lists usually overlap,
so the gather step must combine them into one stream with each logical item
appearing once. :func:`merge_fanout` does exactly that: it concatenates the
per-worker lists in order, identifies each item by a caller-supplied ``key``
function, and keeps the *first* occurrence of each key -- so worker ordering
determines which copy wins and later duplicates are dropped.

The function is pure and order-preserving, and it reports how many duplicates
it discarded so the gather step can surface fan-out overlap in telemetry.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FanoutMerge:
    """The result of merging fan-out lists.

    Attributes:
        merged: The de-duplicated items, in first-seen order.
        dropped: How many duplicate items were discarded.
        keys: The distinct keys of ``merged``, in the same order.
    """

    merged: tuple[Any, ...]
    dropped: int
    keys: tuple[Any, ...]


def merge_fanout(
    result_lists: Iterable[Iterable[Any]], key: Callable[[Any], Any]
) -> FanoutMerge:
    """Merge per-worker result lists, keeping the first item per key.

    Args:
        result_lists: An iterable of the per-worker result iterables.
        key: A callable mapping an item to its de-duplication key; the key must
            be hashable.

    Returns:
        A :class:`FanoutMerge` with the de-duplicated items (first-seen order),
        the count of dropped duplicates, and the distinct keys.

    Raises:
        TypeError: If ``key`` is not callable, ``result_lists`` is not iterable,
            a group is not iterable, or a computed key is not hashable.
    """
    if not callable(key):
        raise TypeError("key must be callable")
    if isinstance(result_lists, (str, bytes)) or not isinstance(
        result_lists, Iterable
    ):
        raise TypeError("result_lists must be an iterable of iterables")

    seen: set[Any] = set()
    merged: list[Any] = []
    keys: list[Any] = []
    dropped = 0

    for index, group in enumerate(result_lists):
        if isinstance(group, (str, bytes)) or not isinstance(group, Iterable):
            raise TypeError(f"result_lists[{index}] must be an iterable")
        for item in group:
            item_key = key(item)
            try:
                already = item_key in seen
            except TypeError as exc:
                raise TypeError(f"key returned an unhashable value: {exc}") from exc
            if already:
                dropped += 1
                continue
            seen.add(item_key)
            merged.append(item)
            keys.append(item_key)

    return FanoutMerge(merged=tuple(merged), dropped=dropped, keys=tuple(keys))
