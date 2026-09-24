from dataclasses import FrozenInstanceError

import pytest

from digital_fte.heartbeat import HEALTHY, STALE, HeartbeatStatus, check_heartbeat


# --- healthy path -----------------------------------------------------------

def test_recent_heartbeat_is_healthy():
    status = check_heartbeat(last_seen=100.0, now=105.0, max_staleness=10.0)
    assert status.state == HEALTHY
    assert status.healthy is True
    assert status.stale is False


def test_staleness_computed():
    status = check_heartbeat(last_seen=100.0, now=107.0, max_staleness=10.0)
    assert status.staleness == 7.0


def test_exactly_at_max_is_healthy():
    status = check_heartbeat(last_seen=100.0, now=110.0, max_staleness=10.0)
    assert status.healthy is True


# --- stale path -------------------------------------------------------------

def test_just_over_max_is_stale():
    status = check_heartbeat(last_seen=100.0, now=110.001, max_staleness=10.0)
    assert status.state == STALE
    assert status.stale is True


def test_far_over_max_is_stale():
    status = check_heartbeat(last_seen=0.0, now=1000.0, max_staleness=10.0)
    assert status.stale
    assert status.staleness == 1000.0


# --- clock skew -------------------------------------------------------------

def test_future_last_seen_is_healthy():
    status = check_heartbeat(last_seen=110.0, now=100.0, max_staleness=10.0)
    assert status.staleness == -10.0
    assert status.healthy is True


# --- record shape -----------------------------------------------------------

def test_returns_status():
    status = check_heartbeat(last_seen=0.0, now=1.0, max_staleness=5.0)
    assert isinstance(status, HeartbeatStatus)
    assert status.max_staleness == 5.0


def test_is_frozen():
    status = check_heartbeat(last_seen=0.0, now=1.0, max_staleness=5.0)
    with pytest.raises(FrozenInstanceError):
        status.state = STALE  # type: ignore[misc]


def test_deterministic():
    a = check_heartbeat(last_seen=1.0, now=2.0, max_staleness=3.0)
    b = check_heartbeat(last_seen=1.0, now=2.0, max_staleness=3.0)
    assert a == b


# --- validation -------------------------------------------------------------

def test_max_staleness_must_be_positive():
    with pytest.raises(ValueError):
        check_heartbeat(last_seen=0.0, now=1.0, max_staleness=0.0)


def test_negative_max_staleness_rejected():
    with pytest.raises(ValueError):
        check_heartbeat(last_seen=0.0, now=1.0, max_staleness=-5.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_now_rejected(bad):
    with pytest.raises(ValueError):
        check_heartbeat(last_seen=0.0, now=bad, max_staleness=5.0)


def test_bool_last_seen_rejected():
    with pytest.raises(TypeError):
        check_heartbeat(last_seen=True, now=1.0, max_staleness=5.0)


def test_string_now_rejected():
    with pytest.raises(TypeError):
        check_heartbeat(last_seen=0.0, now="1", max_staleness=5.0)
