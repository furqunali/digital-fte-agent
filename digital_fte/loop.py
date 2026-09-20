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

    def __init__(self, agents: tuple[Agent, ...], validator: Callable[[str], bool], max_iterations: int = 3) -> None:
        if not agents:
            raise ValueError("at least one agent is required")
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self.agents = agents
        self.validator = validator
        self.max_iterations = max_iterations

    def run(self, task_id: str, initial_state: str) -> LoopResult:
        state = initial_state
        steps: list[LoopStep] = []
        events: list[LoopEvent] = []
        for iteration in range(1, self.max_iterations + 1):
            for agent in self.agents:
                input_state = state
                state = agent.run(LoopContext(task_id, iteration, state))
                steps.append(LoopStep(agent.name, state, iteration))
                events.append(LoopEvent(agent.name, iteration, input_state, state))
            if self.validator(state):
                return LoopResult(task_id, "completed", iteration, tuple(steps), tuple(events), state)
        return LoopResult(task_id, "failed", self.max_iterations, tuple(steps), tuple(events), state)
