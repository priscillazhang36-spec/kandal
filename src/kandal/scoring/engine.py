import math
from datetime import date

from pydantic import BaseModel

from kandal.models.preferences import Preferences
from kandal.models.profile import Profile


class DimensionScore(BaseModel):
    dimension: str
    score: float
    weight: float
    tier: int


class ScoringResult(BaseModel):
    total_score: float
    breakdown: list[DimensionScore]


DIMENSION_WEIGHTS: dict[str, dict] = {
    # Tier 0 — emotional dynamics (core signal)
    "emotional_fit": {"weight": 0.25, "tier": 0},
    # Tier 1 — tag-based
    "interest_overlap": {"weight": 0.08, "tier": 1},
    "personality_match": {"weight": 0.08, "tier": 1},
    "values_alignment": {"weight": 0.08, "tier": 1},
    "lifestyle_signals": {"weight": 0.05, "tier": 1},
    "communication_style": {"weight": 0.03, "tier": 1},
    # Tier 2 — inferred from questionnaire
    "attachment_style": {"weight": 0.06, "tier": 2},
    "love_language_fit": {"weight": 0.04, "tier": 2},
    "conflict_style": {"weight": 0.08, "tier": 2},
    "relationship_history": {"weight": 0.03, "tier": 2},
    # Tier 2 — bazi
    "bazi_compatibility": {"weight": 0.22, "tier": 2},
}


def _jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard similarity. Returns 0.5 when both are empty (neutral)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.5
    union = sa | sb
    return len(sa & sb) / len(union)


# --- Tier 1 scoring functions ---


def _score_interest_overlap(prefs_a: Preferences, prefs_b: Preferences) -> float:
    return _jaccard(prefs_a.interests, prefs_b.interests)


def _score_personality_match(prefs_a: Preferences, prefs_b: Preferences) -> float:
    return _jaccard(prefs_a.personality, prefs_b.personality)


def _score_values_alignment(prefs_a: Preferences, prefs_b: Preferences) -> float:
    return _jaccard(prefs_a.values, prefs_b.values)


def _score_communication_style(prefs_a: Preferences, prefs_b: Preferences) -> float:
    if prefs_a.communication_style == prefs_b.communication_style:
        return 1.0
    if "balanced" in (prefs_a.communication_style, prefs_b.communication_style):
        return 0.5
    return 0.0


def _score_lifestyle_signals(prefs_a: Preferences, prefs_b: Preferences) -> float:
    return _jaccard(prefs_a.lifestyle, prefs_b.lifestyle)


# --- Tier 2 scoring functions ---

ATTACHMENT_MATRIX = {
    ("secure", "secure"): 1.0,
    ("secure", "anxious"): 0.8,
    ("secure", "avoidant"): 0.7,
    ("secure", "disorganized"): 0.5,
    ("anxious", "anxious"): 0.4,
    ("anxious", "avoidant"): 0.0,
    ("anxious", "disorganized"): 0.2,
    ("avoidant", "avoidant"): 0.3,
    ("avoidant", "disorganized"): 0.1,
    ("disorganized", "disorganized"): 0.2,
}


def _score_attachment_style(prefs_a: Preferences, prefs_b: Preferences) -> float:
    a, b = prefs_a.attachment_style, prefs_b.attachment_style
    if a is None or b is None:
        return 0.5
    pair = (a, b) if (a, b) in ATTACHMENT_MATRIX else (b, a)
    return ATTACHMENT_MATRIX.get(pair, 0.5)


_LOVE_LANG_RANK_SCORES = {0: 1.0, 1: 0.75, 2: 0.50, 3: 0.25, 4: 0.10}


def _love_direction_score(giving: list[str], receiving: list[str]) -> float:
    """How well does the giver's #1 language land in the receiver's ranking?"""
    if not giving or not receiving:
        return 0.5
    top_give = giving[0]
    if top_give in receiving:
        return _LOVE_LANG_RANK_SCORES.get(receiving.index(top_give), 0.10)
    return 0.10


def _score_love_language_fit(prefs_a: Preferences, prefs_b: Preferences) -> float:
    a_to_b = _love_direction_score(prefs_a.love_language_giving, prefs_b.love_language_receiving)
    b_to_a = _love_direction_score(prefs_b.love_language_giving, prefs_a.love_language_receiving)
    return (a_to_b + b_to_a) / 2


CONFLICT_MATRIX = {
    ("talk_immediately", "talk_immediately"): 0.7,
    ("talk_immediately", "need_space"): 0.4,
    ("talk_immediately", "avoidant"): 0.1,
    ("talk_immediately", "collaborative"): 0.9,
    ("need_space", "need_space"): 0.6,
    ("need_space", "avoidant"): 0.3,
    ("need_space", "collaborative"): 0.7,
    ("avoidant", "avoidant"): 0.2,
    ("avoidant", "collaborative"): 0.4,
    ("collaborative", "collaborative"): 1.0,
}


def _score_conflict_style(prefs_a: Preferences, prefs_b: Preferences) -> float:
    a, b = prefs_a.conflict_style, prefs_b.conflict_style
    if a is None or b is None:
        return 0.5
    pair = (a, b) if (a, b) in CONFLICT_MATRIX else (b, a)
    return CONFLICT_MATRIX.get(pair, 0.5)


_HISTORY_ORDINAL = {
    "long_term": 3,
    "mostly_casual": 2,
    "recently_out_of_ltr": 1,
    "limited_experience": 0,
}


def _score_relationship_history(prefs_a: Preferences, prefs_b: Preferences) -> float:
    a, b = prefs_a.relationship_history, prefs_b.relationship_history
    if a is None or b is None:
        return 0.5
    return 1.0 - abs(_HISTORY_ORDINAL.get(a, 1) - _HISTORY_ORDINAL.get(b, 1)) / 3


_SCORE_FNS = {
    "interest_overlap": _score_interest_overlap,
    "personality_match": _score_personality_match,
    "values_alignment": _score_values_alignment,
    "communication_style": _score_communication_style,
    "lifestyle_signals": _score_lifestyle_signals,
    "attachment_style": _score_attachment_style,
    "love_language_fit": _score_love_language_fit,
    "conflict_style": _score_conflict_style,
    "relationship_history": _score_relationship_history,
}


def _parse_approx_hour(approx: str | None) -> int | None:
    """Convert '09:00-12:00' to midpoint hour. Returns None if unparseable."""
    if not approx:
        return None
    try:
        start = int(approx.split("-")[0].split(":")[0])
        end = int(approx.split("-")[1].split(":")[0])
        if end < start:
            end += 24
        return ((start + end) // 2) % 24
    except (ValueError, IndexError):
        return None


def _score_bazi_compatibility(
    profile_a: Profile, profile_b: Profile,
) -> float:
    """Score Bazi compatibility. Returns 0.5 (neutral) if either lacks birth data."""
    if not profile_a.birth_date or not profile_b.birth_date:
        return 0.5

    from kandal.scoring.bazi import compute_bazi_profile, score_bazi_compatibility

    hour_a = _parse_approx_hour(profile_a.birth_time_approx)
    hour_b = _parse_approx_hour(profile_b.birth_time_approx)

    bazi_a = compute_bazi_profile(profile_a.birth_date, hour_a)
    bazi_b = compute_bazi_profile(profile_b.birth_date, hour_b)

    return score_bazi_compatibility(bazi_a, bazi_b)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on degenerate input."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    # Cosine similarity is [-1, 1]; rescale to [0, 1]
    return (dot / (norm_a * norm_b) + 1) / 2


def _score_emotional_fit(profile_a: Profile, profile_b: Profile) -> float:
    """Score emotional fit by cross-comparing giving/needs embeddings.

    A's giving style is compared to B's needs, and vice versa.
    Returns 0.5 (neutral) if either user lacks embeddings.
    """
    a_giving = profile_a.emotional_giving_embedding
    a_needs = profile_a.emotional_needs_embedding
    b_giving = profile_b.emotional_giving_embedding
    b_needs = profile_b.emotional_needs_embedding

    scores = []
    # Does A's way of loving match what B needs?
    if a_giving and b_needs:
        scores.append(_cosine_similarity(a_giving, b_needs))
    # Does B's way of loving match what A needs?
    if b_giving and a_needs:
        scores.append(_cosine_similarity(b_giving, a_needs))

    if not scores:
        return 0.5  # neutral when data is missing

    return sum(scores) / len(scores)


def _compute_raw_scores(
    profile_a: Profile, prefs_a: Preferences,
    profile_b: Profile, prefs_b: Preferences,
) -> dict[str, float]:
    """Compute raw (unweighted) score for each dimension. Pure function."""
    raw_scores = {}
    for dim_name in DIMENSION_WEIGHTS:
        if dim_name == "bazi_compatibility":
            raw_scores[dim_name] = _score_bazi_compatibility(profile_a, profile_b)
        elif dim_name == "emotional_fit":
            raw_scores[dim_name] = _score_emotional_fit(profile_a, profile_b)
        else:
            raw_scores[dim_name] = _SCORE_FNS[dim_name](prefs_a, prefs_b)
    return raw_scores


def score_compatibility(
    profile_a: Profile,
    prefs_a: Preferences,
    profile_b: Profile,
    prefs_b: Preferences,
    perspective_weights: dict[str, float] | None = None,
) -> ScoringResult:
    """Compute weighted compatibility score across all dimensions.

    If perspective_weights is provided, uses those instead of global defaults.
    This allows each user to have personalized scoring priorities.
    """
    raw_scores = _compute_raw_scores(profile_a, prefs_a, profile_b, prefs_b)
    weights = perspective_weights or {k: v["weight"] for k, v in DIMENSION_WEIGHTS.items()}

    breakdown = []
    total = 0.0
    for dim_name, meta in DIMENSION_WEIGHTS.items():
        raw = raw_scores[dim_name]
        w = weights.get(dim_name, meta["weight"])
        breakdown.append(
            DimensionScore(
                dimension=dim_name,
                score=raw,
                weight=w,
                tier=meta["tier"],
            )
        )
        total += raw * w
    return ScoringResult(total_score=round(total, 4), breakdown=breakdown)
