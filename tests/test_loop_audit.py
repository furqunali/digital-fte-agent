from digital_fte.loop import LoopOrchestrator
from digital_fte.loop_audit import audit_loop


class Agent:
    name = "planner"
    def run(self, context):
        return context.state + "|done"

def test_audit_loop_counts_execution_telemetry():
    result = LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run("task-1", "start")
    audit = audit_loop(result)
    assert audit.iterations == 1
    assert audit.steps == 1
    assert audit.events == 1
    assert audit.status == "completed"
    assert audit.agents == ("planner",)
