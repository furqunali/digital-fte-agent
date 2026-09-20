from digital_fte.loop import LoopOrchestrator


class Agent:
    name = "planner"

    def run(self, context):
        return context.state + f"|{context.iteration}"


def test_resume_continues_from_persisted_final_state():
    orchestrator = LoopOrchestrator((Agent(),), lambda state: state.endswith("|2"), max_iterations=1)
    first = orchestrator.run("task-1", "start")
    assert first.status == "failed"
    resumed = orchestrator.resume(first, additional_iterations=1)
    assert resumed.status == "completed"
    assert resumed.iterations == 2
    assert [step.iteration for step in resumed.steps] == [1, 2]
    assert [event.input_state for event in resumed.events] == ["start", "start|1"]


def test_resume_does_not_replay_completed_result():
    orchestrator = LoopOrchestrator((Agent(),), lambda state: True)
    result = orchestrator.run("task-2", "start")
    assert orchestrator.resume(result, additional_iterations=5) == result
