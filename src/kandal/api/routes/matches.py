from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from kandal.core.alerts import critical_alert
from kandal.core.supabase import get_supabase
from kandal.schemas.match import MatchRespondRequest, MatchRespondResponse, MatchResponse
from kandal.scripts.match import run_batch

router = APIRouter()


@router.post("/run")
def trigger_matching():
    """Run the batch matching pipeline. Called by Vercel cron or manually."""
    try:
        result = run_batch()
        return result
    except Exception as e:
        critical_alert(f"Daily matching cron failed: {e}", e)
        raise


@router.post("/rescue")
def rescue_conversations():
    """Rescue abandoned profiling conversations. Called by Vercel cron or manually."""
    try:
        from kandal.profiling.rescue import rescue_stale_conversations
        return rescue_stale_conversations()
    except Exception as e:
        critical_alert(f"Rescue cron failed: {e}", e)
        raise


@router.get("/{profile_id}", response_model=list[MatchResponse])
def get_matches(profile_id: UUID):
    """Matches surfaced to this user — pending_review (awaiting their response,
    or theirs in but waiting on the other) and mutual. Hides matches the OTHER
    side declined: rejection sting omitted on purpose.
    """
    client = get_supabase()
    pid = str(profile_id)

    resp_a = (
        client.table("matches").select("*")
        .eq("profile_a_id", pid)
        .in_("status", ["pending_review", "a_accepted", "b_accepted", "mutual"])
        .neq("response_b", "declined")
        .execute()
    )
    resp_b = (
        client.table("matches").select("*")
        .eq("profile_b_id", pid)
        .in_("status", ["pending_review", "a_accepted", "b_accepted", "mutual"])
        .neq("response_a", "declined")
        .execute()
    )
    return resp_a.data + resp_b.data


@router.post("/{match_id}/respond", response_model=MatchRespondResponse)
def respond_to_match(match_id: UUID, body: MatchRespondRequest):
    """User accepts or declines a pending match. Mutual accept → status='mutual'.
    Either decline → status='declined' (the other side never sees it surface)."""
    if body.response not in ("accept", "decline"):
        raise HTTPException(400, "response must be 'accept' or 'decline'")

    client = get_supabase()
    match = (
        client.table("matches").select("*").eq("id", str(match_id)).execute()
    ).data
    if not match:
        raise HTTPException(404, "match not found")
    m = match[0]

    pid = str(body.profile_id)
    if pid == m["profile_a_id"]:
        side = "a"
    elif pid == m["profile_b_id"]:
        side = "b"
    else:
        raise HTTPException(403, "profile_id not part of this match")

    response_value = "accepted" if body.response == "accept" else "declined"
    other_response = m[f"response_{'b' if side == 'a' else 'a'}"]

    if response_value == "declined":
        new_status = "declined"
    elif other_response == "accepted":
        new_status = "mutual"
    elif other_response == "declined":
        new_status = "declined"
    else:
        new_status = f"{side}_accepted"

    now_iso = datetime.now(timezone.utc).isoformat()
    update = {
        f"response_{side}": response_value,
        f"responded_at_{side}": now_iso,
        "status": new_status,
    }
    client.table("matches").update(update).eq("id", str(match_id)).execute()

    return MatchRespondResponse(
        match_id=match_id,
        status=new_status,
        is_mutual=(new_status == "mutual"),
    )
