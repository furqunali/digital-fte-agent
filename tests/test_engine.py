from digital_fte.engine import TaskEngine


def test_engine_writes_dashboard_and_log(tmp_path):
    vault=tmp_path/"vault"; task=vault/"Inbox"/"task.md"; task.parent.mkdir(parents=True); task.write_text("# Update\\n\\nSummarize.",encoding="utf-8")
    result=TaskEngine(vault).process(task)
    assert result.status=="completed" and result.output.exists() and result.log.exists()

def test_engine_creates_vault_directories(tmp_path):
    vault=tmp_path/"vault"; TaskEngine(vault)
    assert all((vault/n).is_dir() for n in ("Inbox","Dashboard","Logs"))
