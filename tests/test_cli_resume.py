from pathlib import Path

from digital_fte.cli import build_parser, main


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


def test_loop_command_persists_result(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["digital-fte", "--state-dir", str(tmp_path), "loop", "task-1", "ready"],
    )

    assert main() == 0
    state = (tmp_path / "task-1.json").read_text(encoding="utf-8")
    assert '"status": "completed"' in state
    assert '"final_state": "ready|planned|executed"' in state
