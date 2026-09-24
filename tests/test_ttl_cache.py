import pytest

from digital_fte.ttl_cache import TtlCache


def test_put_then_get_within_ttl():
    cache = TtlCache(ttl=10.0)
    cache.put("k", now=0.0, value="v")
    assert cache.get("k", now=5.0) == "v"
    assert cache.contains("k", now=5.0) is True


def test_expired_entry_treated_as_absent():
    cache = TtlCache(ttl=10.0)
    cache.put("k", now=0.0, value="v")
    assert cache.contains("k", now=10.0) is False
    assert cache.get("k", now=10.0, default="missing") == "missing"


def test_expiry_is_exclusive_boundary():
    cache = TtlCache(ttl=10.0)
    cache.put("k", now=0.0)
    # present at 9.999, absent at exactly 10.0
    assert cache.contains("k", now=9.999) is True
    assert cache.contains("k", now=10.0) is False


def test_add_dedupe_returns_false_while_live():
    cache = TtlCache(ttl=10.0)
    assert cache.add("k", now=0.0) is True
    assert cache.add("k", now=5.0) is False


def test_add_returns_true_after_expiry():
    cache = TtlCache(ttl=10.0)
    assert cache.add("k", now=0.0) is True
    assert cache.add("k", now=20.0) is True


def test_get_default_when_missing():
    cache = TtlCache(ttl=1.0)
    assert cache.get("nope", now=0.0) is None
    assert cache.get("nope", now=0.0, default=42) == 42


def test_contains_drops_expired_entry():
    cache = TtlCache(ttl=5.0)
    cache.put("k", now=0.0)
    assert len(cache) == 1
    cache.contains("k", now=10.0)  # triggers lazy drop
    assert len(cache) == 0


def test_purge_removes_only_expired():
    cache = TtlCache(ttl=10.0)
    cache.put("a", now=0.0)
    cache.put("b", now=8.0)
    removed = cache.purge(now=12.0)  # 'a' expired at 10, 'b' expires at 18
    assert removed == 1
    assert cache.contains("b", now=12.0) is True


def test_active_keys_preserves_insertion_order():
    cache = TtlCache(ttl=10.0)
    cache.put("a", now=0.0)
    cache.put("b", now=1.0)
    cache.put("c", now=2.0)
    assert cache.active_keys(now=3.0) == ("a", "b", "c")


def test_expires_at_reports_raw_expiry():
    cache = TtlCache(ttl=10.0)
    cache.put("k", now=5.0)
    assert cache.expires_at("k") == 15.0
    assert cache.expires_at("missing") is None


def test_put_overwrites_expiry():
    cache = TtlCache(ttl=10.0)
    cache.put("k", now=0.0)
    cache.put("k", now=100.0)
    assert cache.contains("k", now=105.0) is True


def test_clear_removes_everything():
    cache = TtlCache(ttl=10.0)
    cache.put("k", now=0.0)
    cache.clear()
    assert len(cache) == 0


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_ttl_must_be_positive_finite(bad):
    with pytest.raises(ValueError):
        TtlCache(ttl=bad)


def test_ttl_bool_rejected():
    with pytest.raises(TypeError):
        TtlCache(ttl=True)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_now_must_be_finite(bad):
    cache = TtlCache(ttl=10.0)
    with pytest.raises(ValueError):
        cache.put("k", now=bad)


def test_now_bool_rejected():
    cache = TtlCache(ttl=10.0)
    with pytest.raises(TypeError):
        cache.contains("k", now=True)
