from digital_fte.loop_report_schema import validate_loop_health_report

def test_loop_report_rejects_wrong_completion_ratio():
    payload = {"runs": 5, "completed": 4, "failed": 1, "completion_ratio": 0.5}
    assert not validate_loop_health_report(payload)

def test_loop_report_accepts_zero_runs():
    payload = {"runs": 0, "completed": 0, "failed": 0, "completion_ratio": 0}
    assert validate_loop_health_report(payload)

def test_loop_report_rejects_negative_runs():
    payload = {"runs": -1, "completed": 0, "failed": 0, "completion_ratio": 0}
    assert not validate_loop_health_report(payload)
