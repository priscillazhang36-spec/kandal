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
    # Tier 1 — tag-based
    "interest_overlap": {"weight": 0.18, "tier": 1},
    "personality_match": {"weight": 0.12, "tier": 1},
    "values_alignment": {"weight": 0.12, "tier": 1},
    "lifestyle_signals": {"weight": 0.08, "tier": 1},
    "communication_style": {"weight": 0.05, "tier": 1},
    # Tier 2 — inferred from questionnaire
    "attachment_style": {"weight": 0.18, "tier": 2},
    "love_language_fit": {"weight": 0.12, "tier": 2},
    "conflict_style": {"weight": 0.10, "tier": 2},
    "relationship_history": {"weight": 0.05, "tier": 2},
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


def score_compatibility(
    profile_a: Profile,
    prefs_a: Preferences,
    profile_b: Profile,
    prefs_b: Preferences,
) -> ScoringResult:
    """Pure function. Compute weighted compatibility score across all dimensions."""
    breakdown = []
    total = 0.0
    for dim_name, meta in DIMENSION_WEIGHTS.items():
        raw = _SCORE_FNS[dim_name](prefs_a, prefs_b)
        breakdown.append(
            DimensionScore(
                dimension=dim_name,
                score=raw,
                weight=meta["weight"],
                tier=meta["tier"],
            )
        )
        total += raw * meta["weight"]
    return ScoringResult(total_score=round(total, 4), breakdown=breakdown)
