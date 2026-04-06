from kandal.scoring.engine import DimensionScore, ScoringResult
from kandal.scoring.verdict import compute_verdict


def _make_result(score: float) -> ScoringResult:
    return ScoringResult(total_score=score, breakdown=[])


def test_match_both_open():
    r = _make_result(0.35)
    assert compute_verdict(r, r, "open", "open") == "match"


def test_no_match_one_picky():
    r = _make_result(0.55)
    assert compute_verdict(r, r, "picky", "balanced") == "no_match"


def test_match_both_balanced():
    r = _make_result(0.55)
    assert compute_verdict(r, r, "balanced", "balanced") == "match"


def test_no_match_below_both():
    r = _make_result(0.25)
    assert compute_verdict(r, r, "balanced", "balanced") == "no_match"


def test_asymmetric_scores():
    """User A loves the match but user B doesn't — no match."""
    r_a = _make_result(0.80)
    r_b = _make_result(0.40)
    assert compute_verdict(r_a, r_b, "balanced", "balanced") == "no_match"


def test_asymmetric_scores_both_pass():
    """Both users exceed their own thresholds — match."""
    r_a = _make_result(0.60)
    r_b = _make_result(0.55)
    assert compute_verdict(r_a, r_b, "balanced", "balanced") == "match"
