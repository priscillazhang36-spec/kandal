from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CinderProfile(BaseModel):
    """Row shape for the `cinder_profiles` landing table (migration 00028).

    Thin and forgiving — the seed data is sparse, so nearly everything is
    Optional. Comma-list columns (relationship_intent, qualities, hobbies) stay
    raw `str`; parsing happens in scoring/cinder_prefs.py, not here. Big Five are
    men-only and REAL (half-steps like 4.5) -> float | None.
    """

    id: UUID
    gender: str  # 'man' | 'woman'
    created_at: datetime | None = None
    # Bridge to profiles.id / ideal_types.profile_id (set only for women who
    # completed ideal_type_discovery). NULL for everyone else.
    profile_id: UUID | None = None

    age: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None
    relationship_intent: str | None = None  # comma list
    ethnicity: str | None = None
    politics: str | None = None
    religion: str | None = None
    occupation: str | None = None
    income_range: str | None = None
    mbti: str | None = None

    # Big Five (men only)
    extroversion: float | None = None
    agreeableness: float | None = None
    conscientiousness: float | None = None
    neuroticism: float | None = None
    openness: float | None = None

    qualities: str | None = None  # comma list of trait codes
    hobbies: str | None = None  # comma list of hobby codes
    attractiveness: int | None = None
    intelligence: int | None = None
    social_energy: str | None = None  # extrovert | introvert | in_between
    height: int | None = None
    body_type: str | None = None
    education_level: str | None = None
    has_kids: str | None = None
    wants_kids: str | None = None

    activity_score: int | None = None
    alcohol_score: int | None = None
    smoking_score: int | None = None
    cannabis_score: int | None = None

    preferences_updated_at: datetime | None = None
    preferences: str | None = None  # comma list of FIELD names, priority order
    preference1: str | None = None  # value for priority-1 field
    preference2: str | None = None  # value for priority-2 field
    preference3: str | None = None  # value for priority-3 field
    preference_profile: str | None = None  # women only — freeform paragraph

    # Outreach tracking (men only) — not used by matching
    may_invite: str | None = None
    may_response: str | None = None
    april_invite: str | None = None
    april_response: str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p).strip()
