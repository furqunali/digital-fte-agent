from digital_fte.loop_report_schema import validate_loop_health_report


def _valid_report() -> dict:
    return {"runs": 5, "completed": 4, "failed": 1, "completion_ratio": 0.8}


def test_schema_rejects_bool_as_count():
    payload = _valid_report()
    payload["runs"] = True
    assert not validate_loop_health_report(payload)


def test_schema_rejects_bool_as_ratio():
    payload = _valid_report()
    payload["completion_ratio"] = False
    assert not validate_loop_health_report(payload)
