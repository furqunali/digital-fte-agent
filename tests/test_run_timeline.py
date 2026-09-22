import pytest

from digital_fte.loop import LoopEvent, LoopResult
from digital_fte.run_timeline import (
    AGENT_ACTED,
    ITERATION_COMPLETED,
    ITERATION_STARTED,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_STARTED,
    TIMELINE_KINDS,
    TimelineEvent,
    build_timeline,
    filter_timeline,
    render_timeline,
)


def _result(status="completed", events=(), final_state="c", iterations=2):
    return LoopResult("task", status, iterations, (), tuple(events), final_state)


def _completed_result():
    events = (
        LoopEvent("planner", 1, "a", "b"),
        LoopEvent("validator", 1, "b", "b"),
        LoopEvent("planner", 2, "b", "c"),
    )
    return _result("completed", events, "c", 2)


def test_timeline_kind_ordering_and_sequences():
    timeline = build_timeline(_completed_result())
    kinds = [event.kind for event in timeline]
    assert kinds == [
        RUN_STARTED,
        ITERATION_STARTED,
        AGENT_ACTED,
        AGENT_ACTED,
        ITERATION_COMPLETED,
        ITERATION_STARTED,
        AGENT_ACTED,
        ITERATION_COMPLETED,
        RUN_COMPLETED,
    ]
    assert [event.sequence for event in timeline] == list(range(len(timeline)))


def test_run_started_carries_initial_state_and_terminal_final_state():
    timeline = build_timeline(_completed_result())
    assert timeline[0].kind == RUN_STARTED
    assert timeline[0].to_state == "a"
    assert timeline[0].iteration == 1
    assert timeline[-1].kind == RUN_COMPLETED
    assert timeline[-1].to_state == "c"
    assert timeline[-1].is_terminal


def test_agent_acted_records_states_and_changed_flag():
    timeline = build_timeline(_completed_result())
    acted = filter_timeline(timeline, AGENT_ACTED)
    assert [(e.agent, e.from_state, e.to_state, e.changed) for e in acted] == [
        ("planner", "a", "b", True),
        ("validator", "b", "b", False),
        ("planner", "b", "c", True),
    ]


def test_iteration_markers_group_by_iteration():
    timeline = build_timeline(_completed_result())
    starts = filter_timeline(timeline, ITERATION_STARTED)
    ends = filter_timeline(timeline, ITERATION_COMPLETED)
    assert [e.iteration for e in starts] == [1, 2]
    assert [e.iteration for e in ends] == [1, 2]


def test_failed_status_terminal_kind():
    events = (LoopEvent("planner", 1, "a", "b"),)
    timeline = build_timeline(_result("failed", events, "b", 1))
    assert timeline[-1].kind == RUN_FAILED
    assert timeline[-1].is_terminal


def test_empty_run_is_never_empty():
    timeline = build_timeline(_result("failed", (), "seed", 1))
    assert [e.kind for e in timeline] == [RUN_STARTED, RUN_FAILED]
    assert timeline[0].to_state == "seed"
    assert timeline[0].iteration == 0
    assert timeline[-1].to_state == "seed"


def test_build_timeline_rejects_non_result():
    with pytest.raises(TypeError):
        build_timeline("nope")


def test_build_timeline_rejects_unknown_status():
    with pytest.raises(ValueError):
        build_timeline(_result("running", (), "x", 1))


def test_filter_timeline_rejects_unknown_kind():
    with pytest.raises(ValueError):
        filter_timeline((), "bogus")


def test_filter_timeline_preserves_order():
    timeline = build_timeline(_completed_result())
    acted = filter_timeline(timeline, AGENT_ACTED)
    assert [e.sequence for e in acted] == sorted(e.sequence for e in acted)
    assert all(e.kind == AGENT_ACTED for e in acted)


def test_render_timeline_lines():
    lines = render_timeline(build_timeline(_completed_result()))
    assert lines[0] == "[0] i1 run_started: a"
    assert "planner a -> b" in lines[2]
    assert "validator b == b" in lines[3]
    assert lines[-1] == "[8] i2 run_completed: c"


def test_render_timeline_zero_pads_sequence():
    events = tuple(LoopEvent("a", 1, str(i), str(i + 1)) for i in range(12))
    lines = render_timeline(build_timeline(_result("failed", events, "12", 1)))
    assert lines[0].startswith("[00]")


def test_render_empty_timeline():
    assert render_timeline(()) == ()


def test_timeline_event_rejects_unknown_kind():
    with pytest.raises(ValueError):
        TimelineEvent(0, 0, "mystery")


def test_timeline_event_rejects_negative_sequence():
    with pytest.raises(ValueError):
        TimelineEvent(-1, 0, RUN_STARTED)


def test_timeline_event_rejects_negative_iteration():
    with pytest.raises(ValueError):
        TimelineEvent(0, -1, RUN_STARTED)


def test_timeline_event_rejects_bool_sequence():
    with pytest.raises(TypeError):
        TimelineEvent(True, 0, RUN_STARTED)


def test_agent_acted_requires_agent():
    with pytest.raises(ValueError):
        TimelineEvent(0, 1, AGENT_ACTED, from_state="a", to_state="b", changed=True)


def test_agent_acted_changed_flag_must_be_consistent():
    with pytest.raises(ValueError):
        TimelineEvent(0, 1, AGENT_ACTED, agent="p", from_state="a", to_state="b", changed=False)


def test_non_agent_event_must_not_name_agent():
    with pytest.raises(ValueError):
        TimelineEvent(0, 1, ITERATION_STARTED, agent="p")


def test_all_emitted_kinds_are_registered():
    timeline = build_timeline(_completed_result())
    assert {e.kind for e in timeline} <= TIMELINE_KINDS
