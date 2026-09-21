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


def test_resume_reports_invalid_persisted_schema(tmp_path, monkeypatch, capsys):
    from digital_fte.cli import main

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "task-1.json").write_text(
        '{"task_id":"task-1","status":"completed","iterations":1,"steps":[],"events":[{}],"final_state":"done"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["digital-fte", "--state-dir", str(state_dir), "resume", "task-1"],
    )

    assert main() == 2
    assert '"status": "invalid_state"' in capsys.readouterr().out
