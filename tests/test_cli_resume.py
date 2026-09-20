from pathlib import Path

from digital_fte.cli import build_parser


def test_parser_supports_resume_command():
    args = build_parser().parse_args([
        "--state-dir", "state",
        "resume", "task-1",
        "--additional-iterations", "2",
    ])
    assert args.command == "resume"
    assert args.task_id == "task-1"
    assert args.state_dir == Path("state")
    assert args.additional_iterations == 2
