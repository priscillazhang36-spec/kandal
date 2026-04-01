from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OnboardingSession(BaseModel):
    id: UUID
    phone: str
    state: str = "awaiting_code"
    verification_code: str | None = None
    code_expires_at: datetime | None = None
    code_attempts: int = 0
    profile_id: UUID | None = None
    answers: list[int] = []
    collected_basics: dict = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None
