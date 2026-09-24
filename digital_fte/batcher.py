"""Chunk work into batches bounded by count and/or cumulative size.

Downstream systems rarely want items one at a time nor all at once: an API
takes at most N records per call, a message bus caps a payload's total bytes.
The batcher groups an iterable into consecutive batches that respect a maximum
count per batch, a maximum cumulative size per batch, or both. Item order is
always preserved, and batching is a pure function of the input -- no clock, no
randomness.

Cumulative size is measured with a caller-supplied ``size_of`` function
(default :func:`len`), summed across a batch. An item whose own size exceeds
``max_size`` cannot fit with anything else and is emitted as a batch of one, so
no item is ever dropped.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Iterable


def _validate_optional_count(name: str, value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer or None")
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


def _validate_optional_size(name: str, value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number or None")
    number = float(value)
    if math.isnan(number):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(number):
        raise ValueError(f"{name} must be finite")
    if number <= 0.0:
        raise ValueError(f"{name} must be > 0")
    return number


def _validate_item_size(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("size_of must return a real number")
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        raise ValueError("size_of must return a finite number")
    if number < 0.0:
        raise ValueError("size_of must return a non-negative number")
    return number


def batch(
    items: Iterable,
    *,
    max_count: int | None = None,
    max_size: float | None = None,
    size_of: Callable[[object], float] = len,
) -> tuple[tuple, ...]:
    """Group ``items`` into consecutive batches, order preserved.

    Args:
        items: The iterable to chunk.
        max_count: Maximum number of items per batch (``>= 1``), or ``None``.
        max_size: Maximum cumulative size per batch (positive, finite), or
            ``None``.
        size_of: Callable returning a non-negative finite size for one item;
            used only when ``max_size`` is set. Defaults to :func:`len`.

    Returns:
        A tuple of batches, each a tuple of items. At least one of ``max_count``
        or ``max_size`` must be given. A single item larger than ``max_size`` is
        emitted alone rather than dropped.

    Raises:
        TypeError: an argument has the wrong type, or ``size_of`` is not
            callable / returns a non-number.
        ValueError: neither limit is given, a limit is out of range, or
            ``size_of`` returns a non-finite/negative value.
    """
    max_count = _validate_optional_count("max_count", max_count)
    max_size = _validate_optional_size("max_size", max_size)
    if max_count is None and max_size is None:
        raise ValueError("at least one of max_count or max_size must be given")
    if max_size is not None and not callable(size_of):
        raise TypeError("size_of must be callable")

    batches: list[tuple] = []
    current: list[object] = []
    current_size = 0.0

    for item in items:
        item_size = _validate_item_size(size_of(item)) if max_size is not None else 0.0

        # Would adding this item break a limit? If the current batch is
        # non-empty, close it first.
        if current:
            over_count = max_count is not None and len(current) >= max_count
            over_size = max_size is not None and current_size + item_size > max_size
            if over_count or over_size:
                batches.append(tuple(current))
                current = []
                current_size = 0.0

        current.append(item)
        current_size += item_size

    if current:
        batches.append(tuple(current))
    return tuple(batches)
