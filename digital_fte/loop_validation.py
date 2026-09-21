"""Safety checks for deterministic multi-agent state transitions."""
from __future__ import annotations
from .loop import LoopResult
def validate_loop_result(result: LoopResult) -> tuple[str,...]:
    issues=[]
    if result.status not in {"completed","failed"}: issues.append("invalid status")
    if result.iterations<1: issues.append("iterations must be positive")
    if len(result.steps)!=len(result.events): issues.append("steps and events differ in length")
    for event in result.events:
        if not event.agent.strip(): issues.append("event agent is empty")
        if event.iteration<1: issues.append("event iteration is invalid")
        if not isinstance(event.input_state,str) or not isinstance(event.output_state,str): issues.append("event state is invalid")
    return tuple(dict.fromkeys(issues))
def is_valid_loop_result(result: LoopResult)->bool: return not validate_loop_result(result)
