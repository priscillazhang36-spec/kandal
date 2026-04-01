import math

from kandal.models.preferences import Preferences
from kandal.models.profile import Profile


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

    # Relationship type: must have at least one type in common
    if not set(prefs_a.relationship_types) & set(prefs_b.relationship_types):
        return False

    return True
