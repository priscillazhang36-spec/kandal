from kandal.scoring.engine import DimensionScore, ScoringResult
from kandal.scoring.verdict import compute_verdict


def _make_result(score: float) -> ScoringResult:
    return ScoringResult(total_score=score, breakdown=[])


def test_match_both_open():
    assert compute_verdict(_make_result(0.35), "open", "open") == "match"


def test_no_match_one_picky():
    assert compute_verdict(_make_result(0.55), "picky", "balanced") == "no_match"


def test_match_both_balanced():
    assert compute_verdict(_make_result(0.55), "balanced", "balanced") == "match"


def test_no_match_below_both():
    assert compute_verdict(_make_result(0.25), "balanced", "balanced") == "no_match"
