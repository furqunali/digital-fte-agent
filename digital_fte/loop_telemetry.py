"""Stable JSON contract for multi-agent loop telemetry."""
from __future__ import annotations

import json
from dataclasses import asdict

from digital_fte.loop import LoopResult


def to_json(result: LoopResult) -> str:
    """Serialize a loop result into a deterministic compact JSON document."""
    return json.dumps(asdict(result), sort_keys=True, separators=(",", ":"))
