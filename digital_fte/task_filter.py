"""Tag-based task filtering / querying.

Once tasks are in the intake stage they are frequently labelled with free-form
tags ("billing", "urgent", "customer-x", ...).  When the reasoning loop, a
dashboard, or an operator wants to work on a subset -- "every urgent billing
task that is *not* blocked" -- they need a small, predictable query language.

This module provides that in the dataclass + explicit-validation style used
elsewhere in the package.  A :class:`TagQuery` combines three independent
clauses:

* ``match_any``  -- the task must carry *at least one* of these tags (OR);
* ``require_all`` -- the task must carry *all* of these tags (AND);
* ``exclude``    -- the task must carry *none* of these tags (NOT).

An empty clause imposes no constraint, so an all-empty query matches every
task.  Tags are normalised (trimmed, and case-folded unless ``case_sensitive``)
so that ``"Urgent"``, ``" urgent "`` and ``"urgent"`` are treated alike.

:func:`filter_tasks` applies a query to an iterable of
:class:`~digital_fte.models.Task` objects and returns the matches in the input
order (stable), which keeps downstream ordering -- priority, insertion -- intact.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from .models import Task

TagSource = Mapping[str, Iterable[str]] | Callable[[Task], Iterable[str]]


def _normalize_tag(tag: object, *, case_sensitive: bool) -> str:
    """Validate and canonicalise a single tag."""
    if not isinstance(tag, str):
        raise TypeError(f"tags must be strings, got {type(tag).__name__}")
    cleaned = tag.strip()
    if not cleaned:
        raise ValueError("tags must be non-empty (after stripping whitespace)")
    return cleaned if case_sensitive else cleaned.lower()


def _normalize_tags(tags: object, *, case_sensitive: bool) -> frozenset[str]:
    """Normalise an iterable of tags into a canonical, de-duplicated set."""
    if isinstance(tags, str):
        # A bare string is almost always a mistake -- it would iterate as
        # characters -- so reject it explicitly rather than silently mis-parse.
        raise TypeError("expected an iterable of tags, got a single string")
    if not isinstance(tags, Iterable):
        raise TypeError(f"tags must be iterable, got {type(tags).__name__}")
    return frozenset(
        _normalize_tag(tag, case_sensitive=case_sensitive) for tag in tags
    )


@dataclass(frozen=True)
class TagQuery:
    """A composable predicate over a task's tags.

    The three clauses are combined with logical AND -- a task matches only when
    every non-empty clause is satisfied:

    * ``match_any``   : ``tags & match_any`` is non-empty;
    * ``require_all`` : ``require_all <= tags``;
    * ``exclude``     : ``tags & exclude`` is empty.

    Clauses are supplied as any iterable of tag strings and are normalised on
    construction.  A tag appearing in both ``require_all`` (or ``match_any``)
    and ``exclude`` can never match, which is reported as a ``ValueError``.
    """

    match_any: frozenset[str] = field(default_factory=frozenset)
    require_all: frozenset[str] = field(default_factory=frozenset)
    exclude: frozenset[str] = field(default_factory=frozenset)
    case_sensitive: bool = False

    def __init__(
        self,
        match_any: Iterable[str] = (),
        require_all: Iterable[str] = (),
        exclude: Iterable[str] = (),
        *,
        case_sensitive: bool = False,
    ) -> None:
        cs = bool(case_sensitive)
        any_of = _normalize_tags(match_any, case_sensitive=cs)
        all_of = _normalize_tags(require_all, case_sensitive=cs)
        none_of = _normalize_tags(exclude, case_sensitive=cs)

        contradiction = none_of & (any_of | all_of)
        if contradiction:
            listed = ", ".join(sorted(contradiction))
            raise ValueError(
                f"tag(s) both excluded and required/allowed: {listed}"
            )

        # frozen dataclass: assign through object.__setattr__.
        object.__setattr__(self, "match_any", any_of)
        object.__setattr__(self, "require_all", all_of)
        object.__setattr__(self, "exclude", none_of)
        object.__setattr__(self, "case_sensitive", cs)

    @property
    def is_empty(self) -> bool:
        """``True`` when the query has no clauses and matches everything."""
        return not (self.match_any or self.require_all or self.exclude)

    def matches(self, tags: Iterable[str]) -> bool:
        """Return whether a set of ``tags`` satisfies this query.

        ``tags`` is normalised with the query's own case sensitivity so callers
        may pass raw, mixed-case labels.
        """
        owned = _normalize_tags(tags, case_sensitive=self.case_sensitive)
        if self.match_any and owned.isdisjoint(self.match_any):
            return False
        if self.require_all and not self.require_all <= owned:
            return False
        return not (self.exclude and not owned.isdisjoint(self.exclude))


def _resolve_tags(task: Task, source: TagSource) -> Iterable[str]:
    """Look a task's tags up from a mapping or a callable ``source``."""
    if isinstance(source, Mapping):
        return source.get(task.task_id, ())
    if callable(source):
        return source(task)
    raise TypeError(
        "tags_of must be a mapping of task_id -> tags or a callable"
    )


def filter_tasks(
    tasks: Iterable[Task],
    query: TagQuery,
    tags_of: TagSource,
) -> tuple[Task, ...]:
    """Return the ``tasks`` matching ``query``, preserving input order.

    ``tags_of`` supplies each task's tags either as a mapping keyed by
    ``task_id`` (a missing key means "no tags") or as a callable invoked with
    the :class:`Task`.  The result is a tuple in the same relative order as the
    input, so any prior ordering (priority, FIFO) is preserved.

    Raises :class:`TypeError` for a non-:class:`TagQuery` ``query`` or a
    non-:class:`Task` element.
    """
    if not isinstance(query, TagQuery):
        raise TypeError("query must be a TagQuery")
    result: list[Task] = []
    for task in tasks:
        if not isinstance(task, Task):
            raise TypeError(f"expected Task, got {type(task).__name__}")
        if query.matches(_resolve_tags(task, tags_of)):
            result.append(task)
    return tuple(result)


def partition_tasks(
    tasks: Iterable[Task],
    query: TagQuery,
    tags_of: TagSource,
) -> tuple[tuple[Task, ...], tuple[Task, ...]]:
    """Split ``tasks`` into ``(matching, non_matching)``, preserving order.

    A single pass over ``tasks`` -- handy when the caller needs both the
    selected tasks and the remainder (e.g. to requeue the rest).
    """
    if not isinstance(query, TagQuery):
        raise TypeError("query must be a TagQuery")
    matching: list[Task] = []
    rest: list[Task] = []
    for task in tasks:
        if not isinstance(task, Task):
            raise TypeError(f"expected Task, got {type(task).__name__}")
        target = matching if query.matches(_resolve_tags(task, tags_of)) else rest
        target.append(task)
    return tuple(matching), tuple(rest)
