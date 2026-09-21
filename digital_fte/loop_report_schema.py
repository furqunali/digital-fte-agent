"""Schema validation for exported agent-loop health reports."""
from __future__ import annotations
REQUIRED_FIELDS = frozenset({"runs","completed","failed","completion_ratio"})

def validate_loop_health_report(payload: dict) -> bool:
    if not isinstance(payload, dict) or set(payload) != REQUIRED_FIELDS:
        return False
    if not all(isinstance(payload[name], int) and payload[name] >= 0 for name in ("runs","completed","failed")):
        return False
    ratio = payload["completion_ratio"]
    return isinstance(ratio, (int, float)) and 0 <= ratio <= 1 and payload["completed"] + payload["failed"] == payload["runs"]
