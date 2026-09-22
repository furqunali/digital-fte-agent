"""Schema validation for exported agent-loop health reports."""
from __future__ import annotations

REQUIRED_FIELDS = frozenset({"runs","completed","failed","completion_ratio"})
def validate_loop_health_report(payload: dict) -> bool:
    if not isinstance(payload, dict) or set(payload) != REQUIRED_FIELDS: return False
    if not all(type(payload[name]) is int and payload[name] >= 0 for name in ("runs","completed","failed")): return False
    if payload["completed"] + payload["failed"] != payload["runs"]: return False
    ratio = payload["completion_ratio"]
    if type(ratio) not in (int,float) or not 0 <= ratio <= 1: return False
    expected = payload["completed"] / payload["runs"] if payload["runs"] else 0
    return ratio == expected
