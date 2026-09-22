from dataclasses import dataclass

import pytest

from digital_fte.loop import LoopContext, LoopOrchestrator


@dataclass(frozen=True)
class Planner:
    name: str = "planner"

    def run(self, context: LoopContext) -> str:
        return context.state + "|planned"


@dataclass(frozen=True)
class ValidatorInput:
    calls: int = 0


def test_loop_stops_after_validation_success() -> None:
    calls = ValidatorInput()
    orchestrator = LoopOrchestrator((Planner(),), lambda state: state.endswith("planned"), max_iterations=3)
    result = orchestrator.run("task-1", "received")
    assert result.status == "completed"
    assert result.iterations == 1
    assert result.steps[0].agent == "planner"
    assert result.events[0].input_state == "received"
    assert result.events[0].output_state == "received|planned"


def test_loop_records_failure_after_iteration_limit() -> None:
    orchestrator = LoopOrchestrator((Planner(),), lambda _state: False, max_iterations=2)
    result = orchestrator.run("task-2", "received")
    assert result.status == "failed"
    assert result.iterations == 2
    assert len(result.steps) == 2
    assert len(result.events) == 2
    assert result.events[-1].iteration == 2


def test_loop_requires_agents_and_positive_limit() -> None:
    with pytest.raises(ValueError):
        LoopOrchestrator((), lambda _: True)
    with pytest.raises(ValueError):
        LoopOrchestrator((Planner(),), lambda _: True, max_iterations=0)


def test_loop_rejects_non_integer_limits() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        LoopOrchestrator((Planner(),), lambda _: True, max_iterations=1.5)
    with pytest.raises(ValueError, match="positive integer"):
        LoopOrchestrator((Planner(),), lambda _: True, max_iterations=True)


def test_resume_validates_limit_for_completed_result() -> None:
    orchestrator = LoopOrchestrator((Planner(),), lambda state: True)
    result = orchestrator.run("task", "start")
    import pytest
    with pytest.raises(ValueError, match="positive integer"):
        orchestrator.resume(result, additional_iterations=0)


def test_loop_rejects_non_string_agent_state() -> None:
    @dataclass(frozen=True)
    class BadPlanner:
        name: str = "bad-planner"
        def run(self, context: LoopContext):
            return None
    orchestrator = LoopOrchestrator((BadPlanner(),), lambda _: True)
    with pytest.raises(TypeError, match="must return a string state"):
        orchestrator.run("task", "received")
