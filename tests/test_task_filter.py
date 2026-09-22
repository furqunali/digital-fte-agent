from pathlib import Path

import pytest

from digital_fte.models import Task
from digital_fte.task_filter import (
    TagQuery,
    filter_tasks,
    partition_tasks,
)


def task(task_id, title="t"):
    return Task(source=Path(f"{task_id}.md"), task_id=task_id, title=title, body="body")


# --- TagQuery.matches -------------------------------------------------------


def test_empty_query_matches_everything():
    q = TagQuery()
    assert q.is_empty
    assert q.matches([])
    assert q.matches(["anything", "at", "all"])


def test_match_any_is_or_semantics():
    q = TagQuery(match_any=["billing", "urgent"])
    assert q.matches(["billing"])
    assert q.matches(["urgent", "other"])
    assert not q.matches(["other"])
    assert not q.matches([])


def test_require_all_is_and_semantics():
    q = TagQuery(require_all=["billing", "urgent"])
    assert q.matches(["billing", "urgent", "extra"])
    assert not q.matches(["billing"])
    assert not q.matches(["urgent"])


def test_exclude_is_not_semantics():
    q = TagQuery(exclude=["blocked"])
    assert q.matches(["urgent"])
    assert q.matches([])
    assert not q.matches(["urgent", "blocked"])


def test_clauses_combine_with_and():
    q = TagQuery(match_any=["billing", "sales"], require_all=["urgent"], exclude=["blocked"])
    assert q.matches(["billing", "urgent"])
    assert q.matches(["sales", "urgent", "misc"])
    # missing the require_all tag
    assert not q.matches(["billing"])
    # missing any of match_any
    assert not q.matches(["urgent"])
    # excluded tag present
    assert not q.matches(["billing", "urgent", "blocked"])


def test_case_insensitive_by_default():
    q = TagQuery(match_any=["Urgent"])
    assert q.matches(["URGENT"])
    assert q.matches(["urgent"])
    assert q.matches([" Urgent "])


def test_case_sensitive_mode():
    q = TagQuery(match_any=["Urgent"], case_sensitive=True)
    assert q.matches(["Urgent"])
    assert not q.matches(["urgent"])


def test_whitespace_is_trimmed():
    q = TagQuery(require_all=["  billing  "])
    assert q.matches(["billing"])
    assert q.require_all == frozenset({"billing"})


def test_duplicate_tags_normalized_to_set():
    q = TagQuery(match_any=["a", "a", "A"])
    assert q.match_any == frozenset({"a"})


# --- validation -------------------------------------------------------------


def test_contradictory_query_rejected():
    with pytest.raises(ValueError):
        TagQuery(require_all=["urgent"], exclude=["urgent"])
    with pytest.raises(ValueError):
        TagQuery(match_any=["billing"], exclude=["billing"])
    # case-folding still catches the contradiction
    with pytest.raises(ValueError):
        TagQuery(require_all=["Urgent"], exclude=["urgent"])


def test_empty_or_blank_tag_rejected():
    with pytest.raises(ValueError):
        TagQuery(match_any=[""])
    with pytest.raises(ValueError):
        TagQuery(require_all=["   "])


def test_non_string_tag_rejected():
    with pytest.raises(TypeError):
        TagQuery(match_any=[123])


def test_bare_string_clause_rejected():
    # A single string would iterate as characters -- must be rejected.
    with pytest.raises(TypeError):
        TagQuery(match_any="urgent")


def test_matches_rejects_bare_string_and_non_iterable():
    q = TagQuery(match_any=["a"])
    with pytest.raises(TypeError):
        q.matches("a")
    with pytest.raises(TypeError):
        q.matches(42)


def test_query_is_frozen():
    from dataclasses import FrozenInstanceError

    q = TagQuery(match_any=["a"])
    with pytest.raises(FrozenInstanceError):
        q.match_any = frozenset({"b"})  # type: ignore[misc]


# --- filter_tasks -----------------------------------------------------------


def test_filter_with_mapping_source_preserves_order():
    tasks = [task("t0"), task("t1"), task("t2"), task("t3")]
    tags = {
        "t0": ["urgent", "billing"],
        "t1": ["billing"],
        "t2": ["urgent"],
        "t3": [],
    }
    q = TagQuery(require_all=["urgent"])
    result = filter_tasks(tasks, q, tags)
    assert [t.task_id for t in result] == ["t0", "t2"]


def test_filter_missing_mapping_key_means_no_tags():
    tasks = [task("t0"), task("t1")]
    tags = {"t0": ["urgent"]}  # t1 absent
    q = TagQuery(match_any=["urgent"])
    assert [t.task_id for t in filter_tasks(tasks, q, tags)] == ["t0"]
    # exclude query keeps the untagged task
    q2 = TagQuery(exclude=["urgent"])
    assert [t.task_id for t in filter_tasks(tasks, q2, tags)] == ["t1"]


def test_filter_with_callable_source():
    tasks = [task("a"), task("b")]
    tag_map = {"a": ["x"], "b": ["y"]}
    result = filter_tasks(tasks, TagQuery(match_any=["x"]), lambda t: tag_map[t.task_id])
    assert [t.task_id for t in result] == ["a"]


def test_filter_empty_query_returns_all_in_order():
    tasks = [task("a"), task("b"), task("c")]
    result = filter_tasks(tasks, TagQuery(), {})
    assert [t.task_id for t in result] == ["a", "b", "c"]


def test_filter_returns_tuple():
    result = filter_tasks([], TagQuery(), {})
    assert result == ()
    assert isinstance(result, tuple)


def test_filter_rejects_bad_query_type():
    with pytest.raises(TypeError):
        filter_tasks([task("a")], "not a query", {})


def test_filter_rejects_non_task_element():
    with pytest.raises(TypeError):
        filter_tasks(["not a task"], TagQuery(), {})


def test_filter_rejects_bad_tag_source():
    with pytest.raises(TypeError):
        filter_tasks([task("a")], TagQuery(), 12345)


# --- partition_tasks --------------------------------------------------------


def test_partition_splits_and_preserves_order():
    tasks = [task("t0"), task("t1"), task("t2"), task("t3")]
    tags = {
        "t0": ["urgent"],
        "t1": ["low"],
        "t2": ["urgent"],
        "t3": ["low"],
    }
    q = TagQuery(match_any=["urgent"])
    matching, rest = partition_tasks(tasks, q, tags)
    assert [t.task_id for t in matching] == ["t0", "t2"]
    assert [t.task_id for t in rest] == ["t1", "t3"]


def test_partition_covers_all_input():
    tasks = [task(f"t{i}") for i in range(6)]
    tags = {t.task_id: (["hit"] if i % 2 == 0 else ["miss"]) for i, t in enumerate(tasks)}
    matching, rest = partition_tasks(tasks, TagQuery(match_any=["hit"]), tags)
    assert len(matching) + len(rest) == len(tasks)
    covered = {t.task_id for t in matching} | {t.task_id for t in rest}
    assert covered == {t.task_id for t in tasks}


def test_partition_rejects_bad_query_type():
    with pytest.raises(TypeError):
        partition_tasks([], "nope", {})
