from uuid import uuid4

import pytest

from kandal.models.preferences import Preferences
from kandal.models.profile import Profile


@pytest.fixture
def make_user():
    """Factory fixture returning (Profile, Preferences) with sensible defaults."""

    def _make(
        *,
        age=28,
        gender="female",
        lat=40.7,
        lng=-74.0,
        city="NYC",
        min_age=25,
        max_age=35,
        max_distance_km=50,
        gender_preferences=None,
        relationship_types=None,
        interests=None,
        personality=None,
        values=None,
        communication_style="balanced",
        lifestyle=None,
        selectivity="balanced",
        attachment_style=None,
        love_language_giving=None,
        love_language_receiving=None,
        conflict_style=None,
        relationship_history=None,
    ):
        pid = uuid4()
        profile = Profile(
            id=pid,
            name="Test",
            age=age,
            gender=gender,
            location_lat=lat,
            location_lng=lng,
            city=city,
        )
        prefs = Preferences(
            id=uuid4(),
            profile_id=pid,
            min_age=min_age,
            max_age=max_age,
            max_distance_km=max_distance_km,
            gender_preferences=gender_preferences or [gender],
            relationship_types=relationship_types or ["long_term"],
            interests=interests or [],
            personality=personality or [],
            values=values or [],
            communication_style=communication_style,
            lifestyle=lifestyle or [],
            selectivity=selectivity,
            attachment_style=attachment_style,
            love_language_giving=love_language_giving or [],
            love_language_receiving=love_language_receiving or [],
            conflict_style=conflict_style,
            relationship_history=relationship_history,
        )
        return profile, prefs

    return _make
