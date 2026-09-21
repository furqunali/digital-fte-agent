import json

import pytest

from digital_fte.loop import LoopOrchestrator
from digital_fte.state_store import LoopStateStore


class _Agent:
    name = "planner"

    def run(self, context):
        return context.state + "|done"


def _completed(task_id, state="start"):
    return LoopOrchestrator((_Agent(),), lambda s: s.endswith("|done")).run(
        task_id, state
    )


def _failed(task_id, state="start"):
    result = LoopOrchestrator(
        (_Agent(),), lambda s: False, max_iterations=1
    ).run(task_id, state)
    assert result.status == "failed"
    return result


def test_list_task_ids_is_empty_when_root_missing(tmp_path):
    store = LoopStateStore(tmp_path / "does-not-exist")
    assert store.list_task_ids() == ()
    assert store.load_all() == ()


def test_list_task_ids_returns_sorted_saved_ids(tmp_path):
    store = LoopStateStore(tmp_path)
    store.save(_completed("task-b"))
    store.save(_completed("task-a"))
    store.save(_failed("task-c"))
    assert store.list_task_ids() == ("task-a", "task-b", "task-c")


def test_list_task_ids_ignores_non_json_and_tmp_files(tmp_path):
    store = LoopStateStore(tmp_path)
    store.save(_completed("real"))
    # Stray files that must not be reported as task ids.
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")
    (tmp_path / "real.json.tmp").write_text("{}", encoding="utf-8")
    (tmp_path / "subdir").mkdir()
    assert store.list_task_ids() == ("real",)


def test_load_all_round_trips_every_snapshot(tmp_path):
    store = LoopStateStore(tmp_path)
    first = _completed("task-a", "alpha")
    second = _failed("task-b", "beta")
    store.save(second)
    store.save(first)
    loaded = store.load_all()
    assert loaded == (first, second)  # sorted by task id


def test_load_all_propagates_corrupt_snapshot(tmp_path):
    store = LoopStateStore(tmp_path)
    path = store.save(_completed("task-a"))
    data = json.loads(path.read_text())
    data["status"] = "bogus"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        store.load_all()


def test_load_all_rejects_non_string_final_state(tmp_path):
    store = LoopStateStore(tmp_path)
    path = store.save(_completed("task-a"))
    data = json.loads(path.read_text())
    data["final_state"] = {"unexpected": "object"}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        store.load_all()
