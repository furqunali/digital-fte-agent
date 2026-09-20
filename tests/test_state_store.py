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
