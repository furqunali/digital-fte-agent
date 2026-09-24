"""Validation of agent state transitions against an allowed-transitions map.

A Digital FTE agent moves through a small lifecycle of states, and only certain
moves are legal (``idle -> running``, ``running -> done``, never
``done -> running``). This module checks a proposed move against a declarative
map of ``{state: allowed_next_states}``.

:func:`check_transition` is the pure, non-raising check returning a
:class:`TransitionCheck`; :func:`guard_transition` raises
:class:`IllegalTransition` on an illegal move. :class:`StateMachine` layers a
mutable current-state on top for callers that want to *apply* transitions and
have the machine reject illegal ones.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

# Reasons a check can carry.
REASON_ALLOWED = "allowed"
REASON_NOT_ALLOWED = "not_allowed"
REASON_UNKNOWN_STATE = "unknown_state"


class IllegalTransition(Exception):
    """Raised when a transition is not permitted by the transitions map."""

    def __init__(self, current: str, target: str, reason: str) -> None:
        super().__init__(f"illegal transition {current!r} -> {target!r} ({reason})")
        self.current = current
        self.target = target
        self.reason = reason


def _validate_state(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_transitions(
    transitions: Mapping[str, Iterable[str]]
) -> dict[str, frozenset[str]]:
    if not isinstance(transitions, Mapping):
        raise TypeError("transitions must be a mapping")
    normalised: dict[str, frozenset[str]] = {}
    for state, targets in transitions.items():
        _validate_state("transition source state", state)
        if isinstance(targets, (str, bytes)) or not isinstance(targets, Iterable):
            raise TypeError(f"transitions[{state!r}] must be an iterable of states")
        target_set = set()
        for target in targets:
            target_set.add(_validate_state("transition target state", target))
        normalised[state] = frozenset(target_set)
    return normalised


@dataclass(frozen=True)
class TransitionCheck:
    """The outcome of checking one proposed transition.

    Attributes:
        current: The state being moved from.
        target: The state being moved to.
        allowed: Whether the move is permitted.
        reason: ``"allowed"``, ``"not_allowed"``, or ``"unknown_state"`` (the
            current state is absent from the map).
    """

    current: str
    target: str
    allowed: bool
    reason: str


def check_transition(
    current: str, target: str, transitions: Mapping[str, Iterable[str]]
) -> TransitionCheck:
    """Check ``current -> target`` against ``transitions`` without raising.

    Args:
        current: The current state (non-empty string).
        target: The proposed next state (non-empty string).
        transitions: Map of state to its allowed next states.

    Returns:
        A :class:`TransitionCheck` describing the decision.

    Raises:
        TypeError: If ``transitions`` is malformed.
        ValueError: If ``current`` or ``target`` is empty/not a string.
    """
    current = _validate_state("current", current)
    target = _validate_state("target", target)
    table = _validate_transitions(transitions)

    if current not in table:
        return TransitionCheck(current, target, False, REASON_UNKNOWN_STATE)
    if target in table[current]:
        return TransitionCheck(current, target, True, REASON_ALLOWED)
    return TransitionCheck(current, target, False, REASON_NOT_ALLOWED)


def guard_transition(
    current: str, target: str, transitions: Mapping[str, Iterable[str]]
) -> None:
    """Raise :class:`IllegalTransition` unless ``current -> target`` is allowed.

    The raising counterpart to :func:`check_transition`.
    """
    check = check_transition(current, target, transitions)
    if not check.allowed:
        raise IllegalTransition(check.current, check.target, check.reason)


class StateMachine:
    """A mutable current-state guarded by an allowed-transitions map.

    Args:
        initial: The starting state (must be a key in ``transitions``).
        transitions: Map of state to its allowed next states.
    """

    def __init__(
        self, initial: str, transitions: Mapping[str, Iterable[str]]
    ) -> None:
        self._table = _validate_transitions(transitions)
        initial = _validate_state("initial", initial)
        if initial not in self._table:
            raise ValueError(f"initial state {initial!r} is not in transitions")
        self._state = initial

    @property
    def state(self) -> str:
        """The current state."""
        return self._state

    def can(self, target: str) -> bool:
        """Whether a move to ``target`` is currently legal."""
        return check_transition(self._state, target, self._table).allowed

    def transition(self, target: str) -> str:
        """Apply a move to ``target``, returning the new state.

        Raises:
            IllegalTransition: If the move is not permitted from the current
                state; the machine's state is left unchanged.
        """
        guard_transition(self._state, target, self._table)
        self._state = _validate_state("target", target)
        return self._state
