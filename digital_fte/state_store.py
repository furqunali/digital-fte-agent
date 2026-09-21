"""Deterministic JSON state persistence for multi-agent loops."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from digital_fte.loop import LoopEvent, LoopResult, LoopStep


class LoopStateStore:
    """Persist and restore the latest loop result for a task."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if (
            task_id in {".", ".."}
            or "/" in task_id
            or "\\" in task_id
            or Path(task_id).name != task_id
        ):
            raise ValueError("task_id must be a single path-safe name")

    def save(self, result: LoopResult) -> Path:
        self._validate_task_id(result.task_id)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{result.task_id}.json"
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(asdict(result), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def load(self, task_id: str) -> LoopResult:
        self._validate_task_id(task_id)
        data = json.loads((self.root / f"{task_id}.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("task_id") != task_id:
            raise ValueError("persisted state has an invalid task_id")
        if data.get("status") not in {"completed", "failed"}:
            raise ValueError("persisted state has an invalid status")
        if not isinstance(data.get("iterations"), int) or data["iterations"] < 1:
            raise ValueError("persisted state has invalid iterations")
        steps, events = data.get("steps"), data.get("events")
        if not isinstance(steps, list) or not isinstance(events, list) or len(steps) != len(events):
            raise ValueError("persisted state has inconsistent steps and events")
        try:
            return LoopResult(
                task_id=task_id,
                status=data["status"],
                iterations=data["iterations"],
                steps=tuple(
                    LoopStep(agent=s["agent"], state=s["state"], iteration=s["iteration"])
                    for s in steps
                ),
                events=tuple(
                    LoopEvent(
                        agent=e["agent"],
                        iteration=e["iteration"],
                        input_state=e["input_state"],
                        output_state=e["output_state"],
                    )
                    for e in events
                ),
                final_state=data["final_state"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("persisted state has an invalid schema") from exc
