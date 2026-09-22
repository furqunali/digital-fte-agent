from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class LoopContext:
    task_id: str
    iteration: int
    state: str


@dataclass(frozen=True)
class LoopStep:
    agent: str
    state: str
    iteration: int


@dataclass(frozen=True)
class LoopEvent:
    agent: str
    iteration: int
    input_state: str
    output_state: str


@dataclass(frozen=True)
class LoopResult:
    task_id: str
    status: str
    iterations: int
    steps: tuple[LoopStep, ...]
    events: tuple[LoopEvent, ...]
    final_state: str


class Agent(Protocol):
    name: str

    def run(self, context: LoopContext) -> str: ...


class LoopOrchestrator:
    """Run deterministic agent stages until validation succeeds or a limit is hit."""

    def __init__(
        self,
        agents: tuple[Agent, ...],
        validator: Callable[[str], bool],
        max_iterations: int = 3,
    ) -> None:
        if not agents:
            raise ValueError("at least one agent is required")
        if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")
        self.agents = agents
        self.validator = validator
        self.max_iterations = max_iterations

    def run(self, task_id: str, initial_state: str) -> LoopResult:
        return self._run(
            task_id,
            initial_state,
            start_iteration=1,
            steps=(),
            events=(),
        )

    def resume(self, result: LoopResult, additional_iterations: int = 1) -> LoopResult:
        """Continue an incomplete result without replaying completed iterations."""
        if not isinstance(additional_iterations, int) or isinstance(additional_iterations, bool) or additional_iterations < 1:
            raise ValueError("additional_iterations must be a positive integer")
        if result.status == "completed":
            return result
        return self._run(
            result.task_id,
            result.final_state,
            start_iteration=result.iterations + 1,
            steps=result.steps,
            events=result.events,
            iteration_limit=result.iterations + additional_iterations,
        )

    def _run(
        self,
        task_id: str,
        initial_state: str,
        *,
        start_iteration: int,
        steps: tuple[LoopStep, ...],
        events: tuple[LoopEvent, ...],
        iteration_limit: int | None = None,
    ) -> LoopResult:
        state = initial_state
        step_list = list(steps)
        event_list = list(events)
        limit = iteration_limit if iteration_limit is not None else self.max_iterations
        for iteration in range(start_iteration, limit + 1):
            for agent in self.agents:
                input_state = state
                state = agent.run(LoopContext(task_id, iteration, state))
                if not isinstance(state, str):
                    raise TypeError(f"agent {agent.name!r} must return a string state")
                step_list.append(LoopStep(agent.name, state, iteration))
                event_list.append(LoopEvent(agent.name, iteration, input_state, state))
            if self.validator(state):
                return LoopResult(
                    task_id, "completed", iteration,
                    tuple(step_list), tuple(event_list), state
                )
        return LoopResult(
            task_id, "failed", limit,
            tuple(step_list), tuple(event_list), state
        )
