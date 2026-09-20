from digital_fte.loop import LoopOrchestrator
from digital_fte.loop_audit import audit_loop

class Agent:
    name = "planner"
    def run(self, context):
        return context.state + "|done"

def test_audit_loop_counts_execution_telemetry():
    result = LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run("task-1", "start")
    assert audit_loop(result) == (1, 1, 1, "completed", ("planner",))
