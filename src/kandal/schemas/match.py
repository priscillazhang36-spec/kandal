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
    status: str = "pending_review"
    response_a: str | None = None
    response_b: str | None = None
    created_at: datetime | None = None


class MatchRespondRequest(BaseModel):
    profile_id: UUID  # the user responding (must be a or b)
    response: str     # "accept" | "decline"


class MatchRespondResponse(BaseModel):
    match_id: UUID
    status: str
    is_mutual: bool
