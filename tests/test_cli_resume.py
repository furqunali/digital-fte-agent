from pathlib import Path

import pytest

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


@pytest.mark.parametrize("command", [
    ["loop", "task-1", "ready", "--max-iterations", "0"],
    ["resume", "task-1", "--additional-iterations", "0"],
])
def test_parser_rejects_non_positive_iteration_limits(command):
    with pytest.raises(SystemExit):
        build_parser().parse_args(command)


def test_loop_command_persists_result(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["digital-fte", "--state-dir", str(tmp_path), "loop", "task-1", "ready"],
    )

    assert main() == 0
    state = (tmp_path / "task-1.json").read_text(encoding="utf-8")
    assert '"status":"completed"' in state
    assert '"final_state":"ready|planned|executed"' in state


def test_resume_reports_missing_state_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["digital-fte", "--state-dir", str(tmp_path), "resume", "missing-task"],
    )

    assert main() == 2
    assert capsys.readouterr().out.strip() == '{"task_id": "missing-task", "status": "missing_state"}'


def test_resume_reports_malformed_state_cleanly(tmp_path, monkeypatch, capsys):
    (tmp_path / "broken-task.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["digital-fte", "--state-dir", str(tmp_path), "resume", "broken-task"],
    )

    assert main() == 2
    assert capsys.readouterr().out.strip() == '{"task_id": "broken-task", "status": "invalid_state"}'
