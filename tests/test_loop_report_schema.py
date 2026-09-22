from digital_fte.loop_report_schema import validate_loop_health_report


def test_valid_loop_schema():
    assert validate_loop_health_report({"runs":5,"completed":4,"failed":1,"completion_ratio":0.8})

def test_counts_must_reconcile():
    assert not validate_loop_health_report({"runs":5,"completed":4,"failed":0,"completion_ratio":0.8})
