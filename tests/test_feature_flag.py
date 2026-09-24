import pytest

from digital_fte.feature_flag import (
    BUCKETS,
    FlagDecision,
    bucket_of,
    evaluate_flag,
)


def test_bucket_is_in_range():
    for subject in ["a", "b", "user-123", "tenant/x", "z" * 100]:
        assert 0 <= bucket_of(subject) < BUCKETS


def test_bucket_is_deterministic():
    assert bucket_of("agent-42") == bucket_of("agent-42")


def test_full_rollout_enables_everyone():
    for subject in ["a", "b", "c", "d", "e"]:
        d = evaluate_flag(subject, 100.0)
        assert d.enabled is True
        assert d.reason == "rollout"


def test_zero_rollout_disables_everyone():
    for subject in ["a", "b", "c", "d", "e"]:
        d = evaluate_flag(subject, 0.0)
        assert d.enabled is False
        assert d.reason == "rollout_excluded"


def test_rollout_matches_bucket_threshold():
    subject = "some-subject-id"
    bucket = bucket_of(subject)
    percent = (bucket + 1) / BUCKETS * 100.0  # threshold just above bucket
    d = evaluate_flag(subject, percent)
    assert d.bucket == bucket
    assert d.enabled is True


def test_blocklist_takes_precedence_over_full_rollout():
    d = evaluate_flag("blocked", 100.0, blocklist=["blocked"])
    assert d.enabled is False
    assert d.reason == "blocklist"


def test_allowlist_enables_despite_zero_rollout():
    d = evaluate_flag("vip", 0.0, allowlist=["vip"])
    assert d.enabled is True
    assert d.reason == "allowlist"


def test_blocklist_beats_allowlist():
    d = evaluate_flag("x", 50.0, allowlist=["x"], blocklist=["x"])
    assert d.enabled is False
    assert d.reason == "blocklist"


def test_monotonic_in_rollout_percent():
    # A subject enabled at some percentage stays enabled at higher percentages.
    subject = "monotone-subject"
    enabled_at = None
    for percent in range(0, 101, 5):
        d = evaluate_flag(subject, float(percent))
        if d.enabled and enabled_at is None:
            enabled_at = percent
        if enabled_at is not None:
            assert d.enabled is True


def test_empty_subject_rejected():
    with pytest.raises(ValueError):
        evaluate_flag("", 50.0)


@pytest.mark.parametrize("bad", [-1.0, 101.0, float("nan"), float("inf")])
def test_percent_out_of_range_rejected(bad):
    with pytest.raises(ValueError):
        evaluate_flag("a", bad)


def test_percent_bool_rejected():
    with pytest.raises(TypeError):
        evaluate_flag("a", True)


def test_bad_list_entry_rejected():
    with pytest.raises(ValueError):
        evaluate_flag("a", 50.0, allowlist=["ok", ""])


def test_decision_is_dataclass():
    d = evaluate_flag("a", 50.0)
    assert isinstance(d, FlagDecision)
    assert d.subject_id == "a"
