import math

from kandal.models.preferences import Preferences
from kandal.models.profile import Profile

# Ladders for symmetric tolerance checks.
_INTENT_LADDER = {"casual": 0, "dating": 1, "serious": 2, "marriage_track": 3}
_RELIGION_LADDER = {"not_important": 0, "somewhat": 1, "very": 2}
_SUBSTANCES_LADDER = {"never": 0, "socially": 1, "regularly": 2}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _max_substance_level(prefs: Preferences) -> int | None:
    """Highest substance level the user reports across drinks/smokes/cannabis."""
    levels = [
        _SUBSTANCES_LADDER.get(getattr(prefs, s, None))
        for s in ("drinks", "smokes", "cannabis")
    ]
    levels = [lvl for lvl in levels if lvl is not None]
    return max(levels) if levels else None


def passes_dealbreakers(
    profile_a: Profile,
    prefs_a: Preferences,
    profile_b: Profile,
    prefs_b: Preferences,
) -> bool:
    """Return True if BOTH users pass each other's dealbreakers."""
    # Age: each user's age must be in the other's acceptable range
    if not (prefs_b.min_age <= profile_a.age <= prefs_b.max_age):
        return False
    if not (prefs_a.min_age <= profile_b.age <= prefs_a.max_age):
        return False

    # Gender: each user's gender must be in the other's preferences
    if prefs_b.gender_preferences and profile_a.gender not in prefs_b.gender_preferences:
        return False
    if prefs_a.gender_preferences and profile_b.gender not in prefs_a.gender_preferences:
        return False

    # Distance: skip if either lacks coordinates
    if (
        profile_a.location_lat is not None
        and profile_a.location_lng is not None
        and profile_b.location_lat is not None
        and profile_b.location_lng is not None
    ):
        dist = _haversine_km(
            profile_a.location_lat,
            profile_a.location_lng,
            profile_b.location_lat,
            profile_b.location_lng,
        )
        if dist > min(prefs_a.max_distance_km, prefs_b.max_distance_km):
            return False

    # Legacy relationship_types set intersection — preserved for back-compat
    # against rows that use the older preference shape.
    if not set(prefs_a.relationship_types) & set(prefs_b.relationship_types):
        return False

    # Relationship intent overlap (v4.2). Casual+marriage_track is incompatible;
    # adjacent rungs (casual+dating, dating+serious, serious+marriage_track) pass.
    a_intent = _INTENT_LADDER.get(prefs_a.relationship_intent)
    b_intent = _INTENT_LADDER.get(prefs_b.relationship_intent)
    if a_intent is not None and b_intent is not None and abs(a_intent - b_intent) > 1:
        return False

    # Relationship structure (v4.2). Must match exactly unless one side is
    # "open" (figuring it out — flexes to anything).
    a_struct = prefs_a.relationship_structure
    b_struct = prefs_b.relationship_structure
    if a_struct and b_struct and a_struct != b_struct and "open" not in (a_struct, b_struct):
        return False

    # Religion importance tolerance (v4.2). "very" + "not_important" (gap of 2)
    # is a hard fail; gap of 1 passes.
    a_rel = _RELIGION_LADDER.get(prefs_a.religion_importance)
    b_rel = _RELIGION_LADDER.get(prefs_b.religion_importance)
    if a_rel is not None and b_rel is not None and abs(a_rel - b_rel) >= 2:
        return False

    # Religion match (v4.3). When BOTH users say religion is "very" important
    # AND both have a specific religion stated, require an exact match. This
    # only fires for the high-stakes case — somewhat-religious users pass.
    if (
        a_rel == _RELIGION_LADDER["very"]
        and b_rel == _RELIGION_LADDER["very"]
        and prefs_a.religion
        and prefs_b.religion
        and prefs_a.religion.strip().lower() != prefs_b.religion.strip().lower()
    ):
        return False

    # Wants-kids match-or-flex (v4.2). Only fail when both sides are explicit
    # yes/no AND they differ. maybe/open passes with anything.
    if (
        prefs_a.wants_kids in {"yes", "no"}
        and prefs_b.wants_kids in {"yes", "no"}
        and prefs_a.wants_kids != prefs_b.wants_kids
    ):
        return False

    # Paired partner_wants_kids (v4.2). If A says "no kids in my life," B must
    # not want kids AND not already have them. If A says "yes," B must not be
    # an explicit no on wants_kids (existing kids are fine — possibly a bonus).
    if prefs_a.partner_wants_kids == "no" and (
        prefs_b.wants_kids == "yes" or prefs_b.has_kids == "yes"
    ):
        return False
    if prefs_a.partner_wants_kids == "yes" and prefs_b.wants_kids == "no":
        return False
    if prefs_b.partner_wants_kids == "no" and (
        prefs_a.wants_kids == "yes" or prefs_a.has_kids == "yes"
    ):
        return False
    if prefs_b.partner_wants_kids == "yes" and prefs_a.wants_kids == "no":
        return False

    # Paired partner_substances_max (v4.2). If A's tolerance is "never" but
    # B drinks regularly (or any substance regularly), fail. "open" = no filter.
    a_max_allowed = _SUBSTANCES_LADDER.get(prefs_a.partner_substances_max)
    if a_max_allowed is not None:
        b_max_actual = _max_substance_level(prefs_b)
        if b_max_actual is not None and b_max_actual > a_max_allowed:
            return False
    b_max_allowed = _SUBSTANCES_LADDER.get(prefs_b.partner_substances_max)
    if b_max_allowed is not None:
        a_max_actual = _max_substance_level(prefs_a)
        if a_max_actual is not None and a_max_actual > b_max_allowed:
            return False

    return True
