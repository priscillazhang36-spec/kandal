import json
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class Profile(BaseModel):
    id: UUID
    name: str
    age: int
    gender: str
    location_lat: float | None = None
    location_lng: float | None = None
    city: str | None = None
    bio: str = ""
    is_active: bool = True
    narrative: str | None = None
    narrative_embedding: list[float] | None = None
    profile_version: int = 1
    embedding_version: int = 0
    last_significant_change: datetime | None = None
    birth_date: date | None = None
    birth_time_approx: str | None = None
    birth_city: str | None = None
    emotional_giving: str | None = None
    emotional_needs: str | None = None
    emotional_giving_embedding: list[float] | None = None
    emotional_needs_embedding: list[float] | None = None
    # Spark signals — what creates the initial hit on a first date
    taste_fingerprint: str | None = None
    current_obsession: str | None = None
    two_hour_topic: str | None = None
    contradiction_hook: str | None = None
    past_attraction: str | None = None
    favorite_places: list[dict] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator(
        "narrative_embedding",
        "emotional_giving_embedding",
        "emotional_needs_embedding",
        mode="before",
    )
    @classmethod
    def parse_embedding_string(cls, v: object) -> list[float] | None:
        if isinstance(v, str):
            return json.loads(v)
        return v
