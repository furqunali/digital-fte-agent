from digital_fte.loop import LoopOrchestrator
from digital_fte.loop_telemetry import to_json

class Agent:
    name = "planner"
    def run(self, context):
        return context.state + "|done"

def test_loop_telemetry_is_stable_json():
    result = LoopOrchestrator((Agent(),), lambda state: state.endswith("|done")).run("task-1", "start")
    assert to_json(result) == '{"events":[{"agent":"planner","input_state":"start","iteration":1,"output_state":"start|done"}],"final_state":"start|done","iterations":1,"status":"completed","steps":[{"agent":"planner","iteration":1,"state":"start|done"}],"task_id":"task-1"}'
