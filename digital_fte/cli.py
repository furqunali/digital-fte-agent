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


def build_parser():
    parser = argparse.ArgumentParser(description="Run Digital FTE tasks from a vault")
    parser.add_argument("--vault", type=Path, default=Path("AI_Employee_Vault"))
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="execute a markdown task")
    run.add_argument("task", type=Path)
    loop = sub.add_parser("loop", help="run the deterministic multi-agent loop")
    loop.add_argument("task_id")
    loop.add_argument("state")
    loop.add_argument("--max-iterations", type=int, default=3)
    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "run":
        result = TaskEngine(args.vault).process(args.task)
    else:
        result = LoopOrchestrator(
            (PlannerAgent(), ExecutorAgent()),
            lambda state: state.endswith("|executed"),
            max_iterations=args.max_iterations,
        ).run(args.task_id, args.state)
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
