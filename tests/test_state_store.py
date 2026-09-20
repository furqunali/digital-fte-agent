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
