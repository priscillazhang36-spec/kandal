from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MatchResponse(BaseModel):
    id: UUID
    profile_a_id: UUID
    profile_b_id: UUID
    score: float
    breakdown: dict
    verdict: str
    created_at: datetime | None = None
