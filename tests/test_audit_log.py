import json

import pytest

from digital_fte.audit_log import (
    AUDIT_SCHEMA_VERSION,
    AuditLogError,
    AuditRecord,
    build_audit_records,
    format_audit_log,
    parse_jsonl,
    parse_jsonl_line,
    record_from_timeline_event,
    validate_jsonl,
)
from digital_fte.loop import LoopEvent, LoopResult
from digital_fte.run_timeline import (
    AGENT_ACTED,
    RUN_COMPLETED,
    RUN_STARTED,
    build_timeline,
)


def _completed_result():
    events = (
        LoopEvent("planner", 1, "a", "b"),
        LoopEvent("validator", 1, "b", "b"),
        LoopEvent("planner", 2, "b", "c"),
    )
    return LoopResult("task", "completed", 2, (), events, "c")


# --------------------------------------------------------------------------- #
# AuditRecord validation
# --------------------------------------------------------------------------- #
def test_valid_agent_record_round_trips_through_dict():
    rec = AuditRecord(1, 1, AGENT_ACTED, agent="planner",
                      from_state="a", to_state="b", changed=True)
    assert rec.to_dict() == {
        "v": AUDIT_SCHEMA_VERSION,
        "seq": 1,
        "iteration": 1,
        "kind": AGENT_ACTED,
        "agent": "planner",
        "from_state": "a",
        "to_state": "b",
        "changed": True,
    }


def test_non_agent_record_defaults():
    rec = AuditRecord(0, 0, RUN_STARTED, to_state="a")
    assert rec.agent is None
    assert rec.changed is False


@pytest.mark.parametrize("seq", [-1, True, 1.0, "1"])
def test_bad_seq_rejected(seq):
    with pytest.raises(AuditLogError):
        AuditRecord(seq, 0, RUN_STARTED)


def test_negative_iteration_rejected():
    with pytest.raises(AuditLogError):
        AuditRecord(0, -1, RUN_STARTED)


def test_unknown_kind_rejected():
    with pytest.raises(AuditLogError, match="unknown kind"):
        AuditRecord(0, 0, "teleported")


def test_agent_acted_requires_agent():
    with pytest.raises(AuditLogError, match="require an agent"):
        AuditRecord(0, 0, AGENT_ACTED, from_state="a", to_state="b", changed=True)


def test_changed_must_match_state_delta():
    with pytest.raises(AuditLogError, match="changed must reflect"):
        AuditRecord(0, 0, AGENT_ACTED, agent="p",
                    from_state="a", to_state="b", changed=False)


def test_non_agent_kind_must_not_name_agent():
    with pytest.raises(AuditLogError, match="must not name an agent"):
        AuditRecord(0, 0, RUN_STARTED, agent="p")


def test_bad_schema_version_rejected():
    with pytest.raises(AuditLogError, match="unsupported schema version"):
        AuditRecord(0, 0, RUN_STARTED, version=AUDIT_SCHEMA_VERSION + 1)


def test_non_string_state_rejected():
    with pytest.raises(AuditLogError, match="from_state must be a string"):
        AuditRecord(0, 0, RUN_STARTED, from_state=5)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def test_to_jsonl_is_single_line_and_ordered():
    rec = AuditRecord(2, 1, AGENT_ACTED, agent="p",
                      from_state="a", to_state="b", changed=True)
    line = rec.to_jsonl()
    assert "\n" not in line
    # canonical key order
    assert list(json.loads(line).keys()) == [
        "v", "seq", "iteration", "kind", "agent",
        "from_state", "to_state", "changed",
    ]


def test_to_jsonl_preserves_non_ascii():
    rec = AuditRecord(0, 0, RUN_STARTED, to_state="café")
    assert "café" in rec.to_jsonl()


def test_format_audit_log_has_trailing_newline_per_record():
    records = build_audit_records(_completed_result())
    text = format_audit_log(records)
    assert text.endswith("\n")
    assert len(text.splitlines()) == len(records)


def test_format_empty_is_empty_string():
    assert format_audit_log(()) == ""


def test_format_rejects_non_record():
    with pytest.raises(TypeError):
        format_audit_log([{"seq": 0}])  # type: ignore[list-item]


# --------------------------------------------------------------------------- #
# Timeline integration
# --------------------------------------------------------------------------- #
def test_build_audit_records_matches_timeline():
    result = _completed_result()
    records = build_audit_records(result)
    timeline = build_timeline(result)
    assert len(records) == len(timeline)
    assert records[0].kind == RUN_STARTED
    assert records[-1].kind == RUN_COMPLETED
    assert [r.seq for r in records] == list(range(len(records)))


def test_record_from_timeline_event_type_guard():
    with pytest.raises(TypeError):
        record_from_timeline_event(object())  # type: ignore[arg-type]


def test_build_audit_records_rejects_bad_status():
    bad = LoopResult("t", "running", 1, (), (), "a")
    with pytest.raises(ValueError):
        build_audit_records(bad)


# --------------------------------------------------------------------------- #
# Round-trip parsing
# --------------------------------------------------------------------------- #
def test_round_trip_preserves_records():
    records = build_audit_records(_completed_result())
    text = format_audit_log(records)
    assert parse_jsonl(text) == records


def test_parse_ignores_blank_and_trailing_lines():
    records = build_audit_records(_completed_result())
    text = format_audit_log(records)
    noisy = "\n" + text + "   \n\n"
    assert parse_jsonl(noisy) == records


def test_parse_line_blank_raises():
    with pytest.raises(AuditLogError, match="blank"):
        parse_jsonl_line("   ")


def test_parse_line_invalid_json_raises_with_line_no():
    with pytest.raises(AuditLogError) as exc:
        parse_jsonl_line("{not json", line_no=7)
    assert exc.value.line_no == 7
    assert "invalid JSON" in exc.value.message


def test_parse_rejects_unknown_field():
    line = json.dumps({"v": 1, "seq": 0, "iteration": 0,
                       "kind": RUN_STARTED, "extra": 1})
    with pytest.raises(AuditLogError, match="unknown field"):
        parse_jsonl_line(line)


def test_parse_rejects_missing_version():
    line = json.dumps({"seq": 0, "iteration": 0, "kind": RUN_STARTED})
    with pytest.raises(AuditLogError, match="missing required field: v"):
        parse_jsonl_line(line)


def test_parse_rejects_missing_core_field():
    line = json.dumps({"v": 1, "seq": 0, "kind": RUN_STARTED})
    with pytest.raises(AuditLogError, match="missing required field: iteration"):
        parse_jsonl_line(line)


def test_parse_rejects_non_object_line():
    with pytest.raises(AuditLogError, match="must be a JSON object"):
        parse_jsonl_line("[1, 2, 3]")


def test_parse_propagates_schema_error_with_line_no():
    line = json.dumps({"v": 1, "seq": 0, "iteration": 0, "kind": "bogus"})
    with pytest.raises(AuditLogError) as exc:
        parse_jsonl_line(line, line_no=3)
    assert exc.value.line_no == 3
    assert "unknown kind" in exc.value.message


def test_parse_jsonl_fails_fast():
    good = AuditRecord(0, 0, RUN_STARTED, to_state="a").to_jsonl()
    bad = "{broken"
    with pytest.raises(AuditLogError) as exc:
        parse_jsonl(good + "\n" + bad + "\n")
    assert exc.value.line_no == 2


def test_parse_jsonl_rejects_non_string():
    with pytest.raises(AuditLogError, match="must be a string"):
        parse_jsonl(123)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Whole-document validation (collect-all-errors)
# --------------------------------------------------------------------------- #
def test_validate_clean_document_has_no_errors():
    text = format_audit_log(build_audit_records(_completed_result()))
    assert validate_jsonl(text) == ()


def test_validate_collects_multiple_errors():
    lines = [
        "{broken",  # line 1: bad JSON
        json.dumps({"v": 1, "seq": 1, "iteration": 0, "kind": "nope"}),  # line 2
    ]
    errors = validate_jsonl("\n".join(lines))
    assert len(errors) == 2
    assert {e.line_no for e in errors} == {1, 2}


def test_validate_detects_non_contiguous_seq():
    r0 = AuditRecord(0, 0, RUN_STARTED, to_state="a").to_jsonl()
    r2 = AuditRecord(2, 0, RUN_COMPLETED, to_state="a").to_jsonl()
    errors = validate_jsonl(r0 + "\n" + r2 + "\n")
    assert len(errors) == 1
    assert "non-contiguous seq" in errors[0].message
    assert errors[0].line_no == 2


def test_validate_non_string_input():
    errors = validate_jsonl(None)  # type: ignore[arg-type]
    assert len(errors) == 1
    assert "must be a string" in errors[0].message


def test_error_str_includes_line_prefix():
    assert str(AuditLogError("boom", 4)) == "line 4: boom"
    assert str(AuditLogError("boom")) == "boom"
