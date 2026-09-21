from digital_fte.loop import LoopOrchestrator
from digital_fte.state_store import LoopStateStore


class Agent:
    name = "planner"

    def run(self, context):
        return context.state + "|done"


def test_state_store_round_trips_loop_result(tmp_path):
    result = LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run(
        "task-1", "start"
    )
    store = LoopStateStore(tmp_path)
    path = store.save(result)
    restored = store.load("task-1")
    assert path.name == "task-1.json"
    assert restored == result
    assert not (tmp_path / "task-1.json.tmp").exists()


def test_state_store_replaces_existing_snapshot_atomically(tmp_path):
    store = LoopStateStore(tmp_path)
    first = LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run(
        "task-1", "first"
    )
    second = LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run(
        "task-1", "second"
    )

    store.save(first)
    store.save(second)

    assert store.load("task-1") == second
    assert not (tmp_path / "task-1.json.tmp").exists()


import pytest


@pytest.mark.parametrize("task_id", ["", ".", "..", "../escape", "nested/task", "nested\\task"])
def test_state_store_rejects_unsafe_task_ids(tmp_path, task_id):
    store = LoopStateStore(tmp_path)
    with pytest.raises(ValueError):
        store.load(task_id)


def test_state_store_rejects_tampered_snapshot(tmp_path):
    import json
    store = LoopStateStore(tmp_path)
    path = store.save(LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run("task-1", "start"))
    data = json.loads(path.read_text())
    data["task_id"] = "other-task"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="task_id"):
        store.load("task-1")


def test_state_store_rejects_inconsistent_event_count(tmp_path):
    import json
    store = LoopStateStore(tmp_path)
    path = store.save(LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run("task-1", "start"))
    data = json.loads(path.read_text())
    data["events"] = []
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="steps and events"):
        store.load("task-1")


def test_state_store_rejects_invalid_nested_step_schema(tmp_path):
    import json
    store = LoopStateStore(tmp_path)
    path = store.save(LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run("task-1", "start"))
    data = json.loads(path.read_text())
    data["steps"][0]["iteration"] = "1"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="schema"):
        store.load("task-1")


def test_state_store_rejects_boolean_iterations(tmp_path):
    import json
    store = LoopStateStore(tmp_path)
    path = store.save(
        LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run("task-1", "start")
    )
    data = json.loads(path.read_text())
    data["iterations"] = True
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="iterations"):
        store.load("task-1")
