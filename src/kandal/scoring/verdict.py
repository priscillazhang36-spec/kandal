from kandal.scoring.engine import ScoringResult

SELECTIVITY_THRESHOLDS = {
    "picky": 0.70,
    "balanced": 0.50,
    "open": 0.30,
}


def compute_verdict(
    result_a: ScoringResult,
    result_b: ScoringResult,
    selectivity_a: str,
    selectivity_b: str,
) -> str:
    """Both users must independently exceed their own selectivity threshold,
    scored from their own perspective (using their personalized weights)."""
    thresh_a = SELECTIVITY_THRESHOLDS.get(selectivity_a, 0.50)
    thresh_b = SELECTIVITY_THRESHOLDS.get(selectivity_b, 0.50)
    if result_a.total_score >= thresh_a and result_b.total_score >= thresh_b:
        return "match"
    return "no_match"
