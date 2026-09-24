import pytest

from digital_fte.transition_guard import (
    IllegalTransition,
    StateMachine,
    TransitionCheck,
    check_transition,
    guard_transition,
)

TRANSITIONS = {
    "idle": ["running"],
    "running": ["done", "failed"],
    "failed": ["running"],
    "done": [],
}


def test_allowed_transition():
    c = check_transition("idle", "running", TRANSITIONS)
    assert isinstance(c, TransitionCheck)
    assert c.allowed is True
    assert c.reason == "allowed"


def test_disallowed_transition():
    c = check_transition("idle", "done", TRANSITIONS)
    assert c.allowed is False
    assert c.reason == "not_allowed"


def test_unknown_state():
    c = check_transition("bogus", "running", TRANSITIONS)
    assert c.allowed is False
    assert c.reason == "unknown_state"


def test_terminal_state_has_no_moves():
    c = check_transition("done", "running", TRANSITIONS)
    assert c.allowed is False


def test_guard_allows_legal():
    guard_transition("running", "done", TRANSITIONS)  # no raise


def test_guard_raises_illegal():
    with pytest.raises(IllegalTransition) as exc:
        guard_transition("idle", "done", TRANSITIONS)
    assert exc.value.current == "idle"
    assert exc.value.target == "done"
    assert exc.value.reason == "not_allowed"


def test_empty_state_rejected():
    with pytest.raises(ValueError):
        check_transition("", "running", TRANSITIONS)


def test_bad_transitions_map_rejected():
    with pytest.raises(TypeError):
        check_transition("idle", "running", ["not", "a", "map"])  # type: ignore[arg-type]


def test_bad_target_iterable_rejected():
    with pytest.raises(TypeError):
        check_transition("a", "b", {"a": 123})  # type: ignore[dict-item]


def test_string_targets_rejected_as_iterable():
    # A bare string would iterate as characters; must be rejected.
    with pytest.raises(TypeError):
        check_transition("a", "b", {"a": "running"})


def test_state_machine_happy_path():
    sm = StateMachine("idle", TRANSITIONS)
    assert sm.state == "idle"
    assert sm.can("running") is True
    assert sm.transition("running") == "running"
    assert sm.transition("done") == "done"


def test_state_machine_rejects_illegal_and_keeps_state():
    sm = StateMachine("idle", TRANSITIONS)
    with pytest.raises(IllegalTransition):
        sm.transition("done")
    assert sm.state == "idle"


def test_state_machine_initial_must_be_known():
    with pytest.raises(ValueError):
        StateMachine("nope", TRANSITIONS)


def test_state_machine_can_reflects_current_state():
    sm = StateMachine("idle", TRANSITIONS)
    assert sm.can("done") is False
    sm.transition("running")
    assert sm.can("done") is True
    assert sm.can("failed") is True
