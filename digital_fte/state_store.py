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
        if task_id in {".", ".."} or Path(task_id).name != task_id:
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
        return LoopResult(
            task_id=data["task_id"],
            status=data["status"],
            iterations=data["iterations"],
            steps=tuple(
                LoopStep(agent=step["agent"], state=step["state"], iteration=step["iteration"])
                for step in data["steps"]
            ),
            events=tuple(
                LoopEvent(
                    agent=event["agent"],
                    iteration=event["iteration"],
                    input_state=event["input_state"],
                    output_state=event["output_state"],
                )
                for event in data["events"]
            ),
            final_state=data["final_state"],
        )
