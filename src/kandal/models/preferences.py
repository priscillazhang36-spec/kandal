from uuid import UUID

from pydantic import BaseModel


class Preferences(BaseModel):
    id: UUID
    profile_id: UUID
    min_age: int = 18
    max_age: int = 99
    max_distance_km: int = 50
    gender_preferences: list[str] = []
    relationship_types: list[str] = ["long_term"]
    interests: list[str] = []
    personality: list[str] = []
    values: list[str] = []
    communication_style: str = "balanced"
    lifestyle: list[str] = []
    selectivity: str = "balanced"
    # Tier 2 — inferred from questionnaire
    attachment_style: str | None = None
    love_language_giving: list[str] = []
    love_language_receiving: list[str] = []
    conflict_style: str | None = None
    relationship_history: str | None = None
