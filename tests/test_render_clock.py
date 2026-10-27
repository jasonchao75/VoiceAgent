"""D-073: causal frame brackets never assume symmetric network latency."""

from src.history.render_clock import RenderClockLedger


def test_server_bounds_use_two_actual_render_anchors_without_rtt_halving():
    """Asymmetric delays remain in the measured interval rather than a fake midpoint."""
    now = [100.0]
    ledger = RenderClockLedger(now_ms=lambda: now[0])
    before = ledger.issue("a" * 32, 48000)
    now[0] = 140
    assert ledger.ack(before, "a" * 32, 48000, 1000)
    now[0] = 210
    after = ledger.issue("a" * 32, 48000)
    now[0] = 250
    assert ledger.ack(after, "a" * 32, 48000, 2000)
    result = ledger.bounds("a" * 32, 48000, 1500)
    assert result is not None
    assert (result.lower_ms, result.upper_ms) == (100, 250)
    assert result.anchor_ids == (before, after)
    assert ledger.bounds("b" * 32, 48000, 1500) is None
    assert ledger.bounds("a" * 32, 24000, 1500) is None
    assert ledger.bounds("a" * 32, 48000, 1000) is None


def test_expired_replayed_and_impossible_clock_samples_do_not_create_bounds():
    """A nonce cannot be retargeted or refreshed by delayed or contradictory acknowledgements."""
    now = [0.0]
    ledger = RenderClockLedger(now_ms=lambda: now[0])
    sample = ledger.issue("a" * 32, 48000)
    now[0] = 10
    assert ledger.ack(sample, "a" * 32, 48000, 1000)
    now[0] = 20
    assert ledger.ack(sample, "a" * 32, 48000, 1000)
    assert not ledger.ack(sample, "a" * 32, 48000, 1001)
    old_frame = ledger.issue("a" * 32, 48000)
    now[0] = 30
    assert not ledger.ack(old_frame, "a" * 32, 48000, 999)
    expired = ledger.issue("a" * 32, 48000)
    now[0] = 2031
    assert not ledger.ack(expired, "a" * 32, 48000, 2000)
    assert ledger.bounds("a" * 32, 48000, 1500) is None


def test_clock_probe_budget_is_bounded_and_reclaimed_after_expiration():
    """An authenticated client cannot accumulate unbounded pending probes."""
    import pytest

    now = [0.0]
    ledger = RenderClockLedger(now_ms=lambda: now[0])
    for _ in range(8):
        ledger.issue("a" * 32, 48000)
    with pytest.raises(ValueError, match="pending"):
        ledger.issue("a" * 32, 48000)
    now[0] = 2001
    assert ledger.issue("a" * 32, 48000)
