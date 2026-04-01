from uuid import UUID

from pydantic import BaseModel


class PreferencesCreate(BaseModel):
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


class PreferencesUpdate(BaseModel):
    min_age: int | None = None
    max_age: int | None = None
    max_distance_km: int | None = None
    gender_preferences: list[str] | None = None
    relationship_types: list[str] | None = None
    interests: list[str] | None = None
    personality: list[str] | None = None
    values: list[str] | None = None
    communication_style: str | None = None
    lifestyle: list[str] | None = None
    selectivity: str | None = None


class PreferencesResponse(PreferencesCreate):
    id: UUID
    profile_id: UUID
