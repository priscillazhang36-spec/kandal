from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
    created_at: datetime | None = None
    updated_at: datetime | None = None
