from digital_fte.parser import parse_task

def test_parse_task_is_deterministic(tmp_path):
    p=tmp_path/"task.md"; p.write_text("# Ship report\\n\\nDo the work.",encoding="utf-8")
    assert parse_task(p).task_id==parse_task(p).task_id
    assert parse_task(p).title=="Ship report"
