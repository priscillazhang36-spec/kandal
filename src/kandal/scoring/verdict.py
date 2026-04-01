from kandal.scoring.engine import ScoringResult

SELECTIVITY_THRESHOLDS = {
    "picky": 0.70,
    "balanced": 0.50,
    "open": 0.30,
}


def compute_verdict(
    result: ScoringResult,
    selectivity_a: str,
    selectivity_b: str,
) -> str:
    """Both users must independently exceed their selectivity threshold."""
    thresh_a = SELECTIVITY_THRESHOLDS.get(selectivity_a, 0.50)
    thresh_b = SELECTIVITY_THRESHOLDS.get(selectivity_b, 0.50)
    if result.total_score >= thresh_a and result.total_score >= thresh_b:
        return "match"
    return "no_match"
