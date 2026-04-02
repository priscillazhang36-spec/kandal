from uuid import UUID

from fastapi import APIRouter

from kandal.core.supabase import get_supabase
from kandal.schemas.match import MatchResponse
from kandal.scripts.match import run_batch

router = APIRouter()


@router.post("/run")
def trigger_matching():
    """Run the batch matching pipeline. Called by Vercel cron or manually."""
    result = run_batch()
    return result


@router.get("/{profile_id}", response_model=list[MatchResponse])
def get_matches(profile_id: UUID):
    """Get all matches for a user (appears as either profile_a or profile_b)."""
    client = get_supabase()
    resp_a = client.table("matches").select("*").eq("profile_a_id", str(profile_id)).execute()
    resp_b = client.table("matches").select("*").eq("profile_b_id", str(profile_id)).execute()
    return resp_a.data + resp_b.data
