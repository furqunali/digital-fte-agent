import pytest

from digital_fte.lease import Lease


def test_acquire_sets_expiry():
    lease = Lease.acquire("worker-1", now=100.0, ttl=30.0)
    assert lease.owner == "worker-1"
    assert lease.expires_at == 130.0


def test_is_held_within_ttl():
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    assert lease.is_held(now=5.0) is True
    assert lease.is_expired(now=5.0) is False


def test_expired_after_ttl():
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    assert lease.is_expired(now=10.0) is True
    assert lease.is_held(now=10.0) is False


def test_expiry_boundary_is_inclusive_expired():
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    # exactly at expiry -> expired
    assert lease.is_expired(now=10.0) is True
    assert lease.is_held(now=9.999) is True


def test_remaining_counts_down():
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    assert lease.remaining(now=3.0) == 7.0


def test_remaining_zero_after_expiry():
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    assert lease.remaining(now=100.0) == 0.0


def test_renew_returns_new_lease():
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    renewed = lease.renew(now=5.0, ttl=10.0)
    assert renewed is not lease
    assert renewed.expires_at == 15.0
    assert lease.expires_at == 10.0  # original untouched


def test_renew_can_reclaim_after_expiry():
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    renewed = lease.renew(now=50.0, ttl=10.0)
    assert renewed.is_held(now=55.0) is True


def test_transfer_changes_owner():
    lease = Lease.acquire("old", now=0.0, ttl=10.0)
    transferred = lease.transfer("new", now=20.0, ttl=5.0)
    assert transferred.owner == "new"
    assert transferred.expires_at == 25.0


def test_direct_construction_with_known_expiry():
    lease = Lease(owner="w", expires_at=42.0)
    assert lease.is_held(now=41.0) is True


def test_empty_owner_rejected():
    with pytest.raises(ValueError):
        Lease.acquire("  ", now=0.0, ttl=10.0)


def test_non_string_owner_rejected():
    with pytest.raises(TypeError):
        Lease(owner=5, expires_at=10.0)


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_ttl_must_be_positive_finite(bad):
    with pytest.raises(ValueError):
        Lease.acquire("w", now=0.0, ttl=bad)


def test_ttl_bool_rejected():
    with pytest.raises(TypeError):
        Lease.acquire("w", now=0.0, ttl=True)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_now_must_be_finite(bad):
    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    with pytest.raises(ValueError):
        lease.is_held(now=bad)


def test_now_bool_rejected():
    with pytest.raises(TypeError):
        Lease.acquire("w", now=True, ttl=10.0)


def test_lease_is_frozen():
    from dataclasses import FrozenInstanceError

    lease = Lease.acquire("w", now=0.0, ttl=10.0)
    with pytest.raises(FrozenInstanceError):
        lease.owner = "someone-else"  # type: ignore[misc]
