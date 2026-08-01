"""Guard test: the watchlist verdict can never contradict itself across screens.

The cross-screen bug (CLSK/EQIX/HUT.TO): one renderer showed "✓ In entry zone now"
while another showed "wait, score below 75" for the same stock at the same moment.
Root cause — the entry-zone `signal` (a price fact) and `wl_group` (a full
recommendation) are separate systems; the reconciler only fixed a demoted "ready"
group, so an in-zone stock that was "watching" from the start kept the GO signal.

These tests lock the invariant enforced by verify_watchlist_signal():
  an "in entry zone now" GO signal may appear ONLY with a "ready" group.

Run: python3 test_watchlist_consistency.py
"""
import sys
from intelligence.verification import (
    verify_watchlist_signal,
    assert_watchlist_consistent,
)

IN_ZONE = "✓ In entry zone now"


def _trust(score, dq="full", disq=False):
    return {"total_score": score, "data_quality": dq, "auto_disqualified": disq}


def test_in_zone_below_threshold_is_reconciled():
    # CLSK/EQIX/HUT.TO case: price in zone, score < 75, group "watching".
    for score in (54, 60, 74):
        sig, grp, note = verify_watchlist_signal("X", _trust(score), IN_ZONE, "watching")
        assert "entry zone now" not in sig.lower(), \
            f"score={score}: GO signal survived — {sig!r}"
        assert str(score) in sig and "75" in sig, f"score={score}: unclear wording {sig!r}"
        assert grp == "watching"
        assert_watchlist_consistent(sig, grp)   # must not raise


def test_ready_in_zone_keeps_go_signal():
    # Genuinely ready (in zone AND score >= 75) — the GO signal is correct.
    sig, grp, _ = verify_watchlist_signal("X", _trust(82), IN_ZONE, "ready")
    assert grp == "ready" and "entry zone now" in sig.lower()
    assert_watchlist_consistent(sig, grp)


def test_demoted_ready_is_reconciled():
    # A "ready" group with score < 75 (backstop path) is demoted AND its signal fixed.
    sig, grp, _ = verify_watchlist_signal("X", _trust(70), IN_ZONE, "ready")
    assert grp == "watching" and "entry zone now" not in sig.lower()
    assert_watchlist_consistent(sig, grp)


def test_guard_raises_on_contradiction():
    raised = False
    try:
        assert_watchlist_consistent(IN_ZONE, "watching")
    except AssertionError:
        raised = True
    assert raised, "guard failed to catch a contradictory verdict"


def test_non_zone_signals_pass_through():
    sig, grp, _ = verify_watchlist_signal("X", _trust(60), "Above zone — wait for 8%", "watching")
    assert sig == "Above zone — wait for 8%" and grp == "watching"
    assert_watchlist_consistent(sig, grp)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
