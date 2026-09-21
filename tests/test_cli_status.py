import json

from digital_fte.cli import build_parser, main
from digital_fte.loop import LoopOrchestrator
from digital_fte.state_store import LoopStateStore


class _Agent:
    name = "planner"

    def run(self, context):
        return context.state + "|done"


def _seed(state_dir, task_id, *, ok):
    validator = (lambda s: s.endswith("|done")) if ok else (lambda s: False)
    result = LoopOrchestrator((_Agent(),), validator, max_iterations=1).run(
        task_id, "start"
    )
    LoopStateStore(state_dir).save(result)


def test_cli_status_contract():
    args = build_parser().parse_args(["--state-dir", "state", "status"])
    assert args.command == "status"


def test_status_reports_all_completed(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    _seed(state_dir, "task-a", ok=True)
    _seed(state_dir, "task-b", ok=True)
    monkeypatch.setattr(
        "sys.argv", ["digital-fte", "--state-dir", str(state_dir), "status"]
    )
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "runs": 2,
        "completed": 2,
        "failed": 0,
        "completion_ratio": 1.0,
    }


def test_status_returns_nonzero_when_any_failed(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    _seed(state_dir, "task-a", ok=True)
    _seed(state_dir, "task-b", ok=False)
    monkeypatch.setattr(
        "sys.argv", ["digital-fte", "--state-dir", str(state_dir), "status"]
    )
    assert main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["runs"] == 2
    assert payload["completed"] == 1
    assert payload["failed"] == 1
    assert payload["completion_ratio"] == 0.5


def test_status_is_clean_with_no_persisted_state(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(
        "sys.argv", ["digital-fte", "--state-dir", str(state_dir), "status"]
    )
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "runs": 0,
        "completed": 0,
        "failed": 0,
        "completion_ratio": 0.0,
    }


def test_status_reports_invalid_persisted_state(tmp_path, monkeypatch, capsys):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "task-1.json").write_text(
        '{"task_id":"task-1","status":"completed","iterations":1,'
        '"steps":[],"events":[{}],"final_state":"done"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv", ["digital-fte", "--state-dir", str(state_dir), "status"]
    )
    assert main() == 2
    assert '"status": "invalid_state"' in capsys.readouterr().out
