import pytest

from digital_fte.loop import LoopEvent, LoopResult, LoopStep
from digital_fte.state_diff import StateDiff, diff_states, render_diff


def _step(agent, state, iteration):
    return LoopStep(agent=agent, state=state, iteration=iteration)


def _event(agent, iteration, input_state, output_state):
    return LoopEvent(
        agent=agent,
        iteration=iteration,
        input_state=input_state,
        output_state=output_state,
    )


def _result(task_id="task", status="failed", iterations=1, steps=(), events=(), final="a"):
    return LoopResult(task_id, status, iterations, tuple(steps), tuple(events), final)


def _one_iteration():
    """A minimal single-iteration failed snapshot: a -> b."""
    return _result(
        status="failed",
        iterations=1,
        steps=(_step("planner", "b", 1),),
        events=(_event("planner", 1, "a", "b"),),
        final="b",
    )


def _two_iterations():
    """The one-iteration snapshot resumed to completion: a -> b -> c."""
    return _result(
        status="completed",
        iterations=2,
        steps=(_step("planner", "b", 1), _step("planner", "c", 2)),
        events=(_event("planner", 1, "a", "b"), _event("planner", 2, "b", "c")),
        final="c",
    )


# --- identity / no-op -------------------------------------------------------


def test_identical_snapshots_are_noop():
    result = _two_iterations()
    diff = diff_states(result, result)
    assert diff.is_noop
    assert not diff.has_changes
    assert not diff.is_progression
    assert not diff.is_rewind
    assert not diff.is_divergence
    assert diff.iterations_delta == 0
    assert diff.steps_added == ()
    assert diff.events_added == ()
    assert diff.agents_engaged == ()


def test_noop_renders_single_line():
    result = _one_iteration()
    lines = render_diff(diff_states(result, result))
    assert lines == ("diff task: noop (+0 iterations)",)


# --- progression (append) ---------------------------------------------------


def test_progression_records_only_additions():
    diff = diff_states(_one_iteration(), _two_iterations())
    assert diff.is_progression
    assert diff.has_changes
    assert not diff.is_rewind
    assert not diff.is_divergence
    assert diff.iterations_delta == 1
    assert diff.status_changed
    assert diff.status_before == "failed"
    assert diff.status_after == "completed"
    assert diff.final_state_changed
    assert diff.final_state_before == "b"
    assert diff.final_state_after == "c"
    assert diff.events_removed == ()
    assert diff.steps_removed == ()
    assert diff.events_added == (_event("planner", 2, "b", "c"),)
    assert diff.steps_added == (_step("planner", "c", 2),)


def test_progression_agents_engaged_first_seen_order():
    before = _one_iteration()
    after = _result(
        status="completed",
        iterations=2,
        steps=(_step("planner", "b", 1), _step("critic", "c", 2), _step("planner", "d", 2)),
        events=(
            _event("planner", 1, "a", "b"),
            _event("critic", 2, "b", "c"),
            _event("planner", 2, "c", "d"),
        ),
        final="d",
    )
    diff = diff_states(before, after)
    assert diff.agents_engaged == ("critic", "planner")


def test_progression_render_prefixes_added_events():
    lines = render_diff(diff_states(_one_iteration(), _two_iterations()))
    assert lines[0] == "diff task: progression (+1 iterations)"
    assert "status: failed -> completed" in lines
    assert "final_state: b -> c" in lines
    assert lines[-1] == "+ i2 planner: b -> c"
    assert not any(line.startswith("- ") for line in lines)


# --- rewind (prefix drop) ---------------------------------------------------


def test_rewind_records_only_removals():
    diff = diff_states(_two_iterations(), _one_iteration())
    assert diff.is_rewind
    assert not diff.is_progression
    assert not diff.is_divergence
    assert diff.iterations_delta == -1
    assert diff.events_added == ()
    assert diff.steps_added == ()
    assert diff.events_removed == (_event("planner", 2, "b", "c"),)
    assert diff.steps_removed == (_step("planner", "c", 2),)
    assert diff.agents_engaged == ()


def test_rewind_render_prefixes_removed_events():
    lines = render_diff(diff_states(_two_iterations(), _one_iteration()))
    assert lines[0] == "diff task: rewind (-1 iterations)"
    assert "- i2 planner: b -> c" in lines
    assert not any(line.startswith("+ ") for line in lines)


# --- divergence (shared prefix then differ) ---------------------------------


def test_divergence_records_both_sides_beyond_common_prefix():
    before = _two_iterations()  # a->b, b->c
    after = _result(
        status="completed",
        iterations=2,
        steps=(_step("planner", "b", 1), _step("critic", "z", 2)),
        events=(_event("planner", 1, "a", "b"), _event("critic", 2, "b", "z")),
        final="z",
    )
    diff = diff_states(before, after)
    assert diff.is_divergence
    assert not diff.is_progression
    assert not diff.is_rewind
    # shared prefix is the first (planner a->b) event; both second events differ.
    assert diff.events_removed == (_event("planner", 2, "b", "c"),)
    assert diff.events_added == (_event("critic", 2, "b", "z"),)
    assert diff.agents_engaged == ("critic",)


def test_divergence_render_lists_removals_before_additions():
    before = _two_iterations()
    after = _result(
        status="completed",
        iterations=2,
        steps=(_step("planner", "b", 1), _step("critic", "z", 2)),
        events=(_event("planner", 1, "a", "b"), _event("critic", 2, "b", "z")),
        final="z",
    )
    lines = render_diff(diff_states(before, after))
    assert lines[0].startswith("diff task: divergence")
    minus = next(i for i, line in enumerate(lines) if line.startswith("- "))
    plus = next(i for i, line in enumerate(lines) if line.startswith("+ "))
    assert minus < plus


# --- state-only changes -----------------------------------------------------


def test_status_or_final_change_without_step_change_is_not_noop():
    before = _result(status="failed", iterations=1, final="x")
    after = _result(status="completed", iterations=1, final="x")
    diff = diff_states(before, after)
    assert not diff.is_noop
    assert diff.status_changed
    assert not diff.final_state_changed
    # No steps/events moved, so it is neither progression nor rewind.
    assert not diff.is_progression
    assert not diff.is_rewind
    assert not diff.is_divergence


def test_diff_uses_after_task_id():
    diff = diff_states(_one_iteration(), _two_iterations())
    assert diff.task_id == "task"


# --- validation / edge cases ------------------------------------------------


def test_diff_rejects_mismatched_task_ids():
    before = _result(task_id="alpha")
    after = _result(task_id="beta")
    with pytest.raises(ValueError, match="different tasks"):
        diff_states(before, after)


def test_diff_rejects_non_result_before():
    with pytest.raises(TypeError):
        diff_states("nope", _one_iteration())


def test_diff_rejects_non_result_after():
    with pytest.raises(TypeError):
        diff_states(_one_iteration(), "nope")


def test_empty_snapshots_diff_to_noop():
    empty = _result(status="failed", iterations=1, steps=(), events=(), final="seed")
    diff = diff_states(empty, empty)
    assert diff.is_noop
    assert render_diff(diff) == ("diff task: noop (+0 iterations)",)


def test_from_empty_to_populated_is_progression():
    empty = _result(status="failed", iterations=1, steps=(), events=(), final="a")
    diff = diff_states(empty, _one_iteration())
    assert diff.is_progression
    assert diff.events_added == (_event("planner", 1, "a", "b"),)
    assert diff.events_removed == ()


def test_state_diff_is_frozen():
    diff = diff_states(_one_iteration(), _two_iterations())
    with pytest.raises(AttributeError):
        diff.task_id = "other"  # type: ignore[misc]


def test_render_is_deterministic():
    a, b = _one_iteration(), _two_iterations()
    assert render_diff(diff_states(a, b)) == render_diff(diff_states(a, b))


def test_diff_result_type():
    assert isinstance(diff_states(_one_iteration(), _two_iterations()), StateDiff)
