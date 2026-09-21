from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .engine import TaskEngine
from .loop import LoopContext, LoopOrchestrator


@dataclass(frozen=True)
class PlannerAgent:
    name: str = "planner"

    def run(self, context: LoopContext) -> str:
        return context.state if context.state.endswith("|planned") else context.state + "|planned"


@dataclass(frozen=True)
class ExecutorAgent:
    name: str = "executor"

    def run(self, context: LoopContext) -> str:
        return context.state if context.state.endswith("|executed") else context.state + "|executed"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def build_parser():
    parser = argparse.ArgumentParser(description="Run Digital FTE tasks from a vault")
    parser.add_argument("--vault", type=Path, default=Path("AI_Employee_Vault"))
    parser.add_argument("--state-dir", type=Path, default=Path("AI_Employee_Vault/State"))
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="execute a markdown task")
    run.add_argument("task", type=Path)
    loop = sub.add_parser("loop", help="run the deterministic multi-agent loop")
    loop.add_argument("task_id")
    loop.add_argument("state")
    loop.add_argument("--max-iterations", type=_positive_int, default=3)
    resume = sub.add_parser("resume", help="resume a persisted multi-agent loop")
    resume.add_argument("task_id")
    resume.add_argument("--additional-iterations", type=_positive_int, default=1)
    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "run":
        result = TaskEngine(args.vault).process(args.task)
    elif args.command == "loop":
        from .state_store import LoopStateStore

        result = LoopOrchestrator(
            (PlannerAgent(), ExecutorAgent()),
            lambda state: state.endswith("|executed"),
            max_iterations=args.max_iterations,
        ).run(args.task_id, args.state)
        LoopStateStore(args.state_dir).save(result)
    else:
        from .state_store import LoopStateStore

        store = LoopStateStore(args.state_dir)
        try:
            persisted = store.load(args.task_id)
        except FileNotFoundError:
            print(json.dumps({"task_id": args.task_id, "status": "missing_state"}))
            return 2
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            print(json.dumps({"task_id": args.task_id, "status": "invalid_state"}))
            return 2
        result = LoopOrchestrator(
            (PlannerAgent(), ExecutorAgent()),
            lambda state: state.endswith("|executed"),
        ).resume(persisted, args.additional_iterations)
        store.save(result)
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
