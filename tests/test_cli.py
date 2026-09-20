from digital_fte.cli import build_parser

def test_cli_run_contract():
    args = build_parser().parse_args(["--vault", "vault", "run", "task.md"])
    assert args.command == "run"
    assert str(args.task) == "task.md"

def test_cli_loop_contract():
    args = build_parser().parse_args(["loop", "task-1", "queued", "--max-iterations", "2"])
    assert args.command == "loop"
    assert args.task_id == "task-1"
    assert args.max_iterations == 2
