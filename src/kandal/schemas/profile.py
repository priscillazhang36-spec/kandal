from uuid import UUID

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    name: str
    age: int = Field(ge=18)
    gender: str
    location_lat: float | None = None
    location_lng: float | None = None
    city: str | None = None
    bio: str = ""


class ProfileUpdate(BaseModel):
    name: str | None = None
    age: int | None = Field(default=None, ge=18)
    gender: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    city: str | None = None
    bio: str | None = None
    is_active: bool | None = None


class ProfileResponse(BaseModel):
    id: UUID
    name: str
    age: int
    gender: str
    city: str | None = None
    bio: str = ""
    is_active: bool = True
