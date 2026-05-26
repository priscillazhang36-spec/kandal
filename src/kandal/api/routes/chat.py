"""Web chat API — replaces SMS for the profiling conversation."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kandal.core.supabase import get_supabase
from kandal.profiling.engine import ProfilingEngine
from kandal.sms.handler import route_message

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatStartRequest(BaseModel):
    phone: str  # E.164 format, e.g. "+15551234567"
    mode: str = "ideal_type_discovery"  # or "full_discovery"


class ChatStartResponse(BaseModel):
    session_id: str
    message: str


class ChatReplyRequest(BaseModel):
    session_id: str
    message: str


class ChatReplyResponse(BaseModel):
    message: str
    is_complete: bool = False


class KandalChatRequest(BaseModel):
    phone: str | None = None
    profile_id: str | None = None
    message: str


class KandalChatResponse(BaseModel):
    reply: str
    memories_written: int


@router.post("/kandal/chat", response_model=KandalChatResponse)
def kandal_chat(body: KandalChatRequest):
    """Ongoing post-onboarding Kandal chat. Identify user by phone or profile_id."""
    from kandal.profiling.chat import ProfileMissingError, chat_turn

    if not body.phone and not body.profile_id:
        raise HTTPException(400, "phone or profile_id required")

    profile_id = body.profile_id
    if not profile_id:
        client = get_supabase()
        resp = client.table("profiles").select("id").eq("phone", body.phone).execute()
        if not resp.data:
            raise HTTPException(404, "profile not found")
        profile_id = resp.data[0]["id"]

    try:
        result = chat_turn(UUID(str(profile_id)), body.message)
    except ProfileMissingError:
        raise HTTPException(404, "profile not found")
    except Exception as e:
        logger.exception("kandal chat failed")
        raise HTTPException(500, f"chat failed: {e}")

    return KandalChatResponse(reply=result.reply, memories_written=result.memories_written)


@router.post("/chat/start", response_model=ChatStartResponse)
def chat_start(body: ChatStartRequest):
    """Start a web chat profiling session. Returns opening message.

    Mode controls which engine drives the session:
      - "full_discovery": user-centric profile elicitation, becomes matchable.
      - "ideal_type_discovery" (default): partner-clarity exercise, does NOT
        flip is_active or write a preferences row.
    """
    client = get_supabase()
    phone = body.phone

    # Create profile
    profile_resp = client.table("profiles").select("id").eq("phone", phone).execute()
    if profile_resp.data:
        profile_id = profile_resp.data[0]["id"]
    else:
        resp = client.table("profiles").insert(
            {"phone": phone, "is_active": False}
        ).execute()
        profile_id = resp.data[0]["id"]

    if body.mode == "ideal_type_discovery":
        from kandal.profiling.ideal_type_engine import IdealTypeEngine

        engine = IdealTypeEngine()
        state, opening = engine.start(UUID(str(profile_id)))

        row_resp = client.table("ideal_types").insert({
            "profile_id": str(profile_id),
            "messages": state.messages,
            "stage": state.stage,
            "sub_state": _serialize_ideal_sub_state(state),
        }).execute()

        session_resp = client.table("onboarding_sessions").upsert(
            {
                "phone": phone,
                "state": "ideal_type_discovery",
                "mode": "ideal_type_discovery",
                "verification_code": None,
                "code_expires_at": None,
                "code_attempts": 0,
                "profile_id": str(profile_id),
                "answers": [],
                "collected_basics": {},
                "conversation_id": row_resp.data[0]["id"],
            },
            on_conflict="phone",
        ).execute()

        session_id = session_resp.data[0]["id"]
        return ChatStartResponse(session_id=str(session_id), message=opening)

    # Default branch: full_discovery (existing behavior)
    engine = ProfilingEngine()
    state, opening = engine.start(UUID(str(profile_id)))

    conv_resp = client.table("profiling_conversations").insert({
        "profile_id": str(profile_id),
        "messages": state.messages,
        "coverage": state.coverage,
        "status": "in_progress",
    }).execute()

    session_resp = client.table("onboarding_sessions").upsert(
        {
            "phone": phone,
            "state": "adaptive_profiling",
            "mode": "full_discovery",
            "verification_code": None,
            "code_expires_at": None,
            "code_attempts": 0,
            "profile_id": str(profile_id),
            "answers": [],
            "collected_basics": {},
            "conversation_id": conv_resp.data[0]["id"],
        },
        on_conflict="phone",
    ).execute()

    session_id = session_resp.data[0]["id"]
    return ChatStartResponse(session_id=str(session_id), message=opening)


def _serialize_ideal_sub_state(state) -> dict:
    """Pack ideal-type engine state fields that aren't already top-level columns."""
    return {
        "dealbreaker_index": state.dealbreaker_index,
        "dealbreaker_answers": state.dealbreaker_answers,
        "celebrity_pairs": state.celebrity_pairs,
        "celebrity_pair_index": state.celebrity_pair_index,
        "questions_asked": state.questions_asked,
        "last_coverage_check_turn": state.last_coverage_check_turn,
        "vignette_index": state.vignette_index,
        "vignette_replies": state.vignette_replies,
        "pending_artifact": state.pending_artifact,
    }


@router.post("/chat/reply", response_model=ChatReplyResponse)
def chat_reply(body: ChatReplyRequest):
    """Send a message in a web chat session. Returns the reply."""
    client = get_supabase()

    # Load session by ID
    resp = client.table("onboarding_sessions").select("*").eq(
        "id", body.session_id
    ).execute()
    if not resp.data:
        raise HTTPException(404, "Session not found")

    session = resp.data[0]
    phone = session["phone"]

    # Route through existing state machine (without sending SMS)
    reply = _route_without_sms(phone, body.message)

    # Check if session is now complete
    updated = client.table("onboarding_sessions").select("state").eq(
        "id", body.session_id
    ).execute()
    is_complete = updated.data[0]["state"] == "complete" if updated.data else False

    return ChatReplyResponse(message=reply, is_complete=is_complete)


def _route_without_sms(phone: str, body: str) -> str:
    """Run the state machine but skip the send_sms call."""
    from kandal.models.onboarding import OnboardingSession
    from kandal.sms.handler import (
        _handle_adaptive_profiling,
        _handle_collecting_age,
        _handle_collecting_city,
        _handle_collecting_gender,
        _handle_collecting_gender_preference,
        _handle_collecting_name,
        _handle_question,
        _load_session,
        _finalize,
        _save_session,
    )
    from kandal.sms import messages
    from kandal.questionnaire import QUESTIONS

    session = _load_session(phone)
    if session is None:
        return messages.RESTART_HINT

    state = session.state

    if state == "ideal_type_discovery":
        reply = _handle_ideal_type(session, body)
    elif state == "adaptive_profiling":
        reply = _handle_adaptive_profiling(session, body)
    elif state.startswith("onboarding_q"):
        q_index = int(state.replace("onboarding_q", "")) - 1
        reply = _handle_question(session, body, q_index)
    elif state == "collecting_name":
        reply = _handle_collecting_name(session, body)
    elif state == "collecting_age":
        reply = _handle_collecting_age(session, body)
    elif state == "collecting_gender":
        reply = _handle_collecting_gender(session, body)
    elif state == "collecting_gender_preference":
        reply = _handle_collecting_gender_preference(session, body)
    elif state == "collecting_city":
        reply = _handle_collecting_city(session, body)
    elif state == "finalize_failed":
        if body.strip().lower() == "retry":
            if _finalize(session):
                session.state = "complete"
                _save_session(session)
                reply = messages.ONBOARDING_COMPLETE
            else:
                reply = messages.FINALIZE_FAILED
        else:
            reply = messages.FINALIZE_FAILED
    elif state == "complete":
        try:
            from kandal.profiling.chat import chat_turn
            reply = chat_turn(session.profile_id, body).reply
        except Exception as e:
            logger.error("kandal chat_turn failed for %s: %s", phone, e)
            reply = messages.ALREADY_COMPLETE
    elif state == "ideal_type_complete":
        reply = (
            "Your ideal-type session is locked in. Come back anytime to refine it."
        )
    elif state == "expired":
        reply = messages.SESSION_EXPIRED
    else:
        reply = messages.RESTART_HINT

    logger.info("web_chat phone=%s state=%s body=%r reply=%r", phone, state, body, reply[:80])
    return reply


def _handle_ideal_type(session, body: str) -> str:
    """Drive one turn of the ideal_type_discovery flow. Persists state changes."""
    from datetime import datetime, timezone
    from kandal.profiling.ideal_type_engine import (
        IdealTypeEngine,
        IdealTypeState,
    )
    from kandal.sms.handler import _save_session

    client = get_supabase()
    row_resp = client.table("ideal_types").select("*").eq(
        "id", str(session.conversation_id)
    ).execute()
    if not row_resp.data:
        logger.error("ideal_types row missing for session %s", session.id)
        return "Session lost — please start again."

    row = row_resp.data[0]
    sub = row.get("sub_state") or {}

    state = IdealTypeState(
        profile_id=UUID(str(session.profile_id)),
        messages=row.get("messages") or [],
        stage=row.get("stage") or "dealbreakers",
        dealbreaker_index=sub.get("dealbreaker_index", 0),
        dealbreaker_answers=sub.get("dealbreaker_answers") or {},
        celebrity_pairs=sub.get("celebrity_pairs") or [],
        celebrity_pair_index=sub.get("celebrity_pair_index", 0),
        celebrity_choices=row.get("celebrity_choices") or [],
        questions_asked=sub.get("questions_asked", 0),
        last_coverage_check_turn=sub.get("last_coverage_check_turn", -1),
        vignettes=row.get("vignettes") or [],
        vignette_index=sub.get("vignette_index", 0),
        vignette_replies=sub.get("vignette_replies") or [],
        pending_artifact=sub.get("pending_artifact"),
    )

    engine = IdealTypeEngine()
    turn = engine.next_turn(state, body)

    update_data = {
        "messages": state.messages,
        "stage": state.stage,
        "vignettes": state.vignettes,
        "celebrity_choices": state.celebrity_choices,
        "sub_state": {
            "dealbreaker_index": state.dealbreaker_index,
            "dealbreaker_answers": state.dealbreaker_answers,
            "celebrity_pairs": state.celebrity_pairs,
            "celebrity_pair_index": state.celebrity_pair_index,
            "questions_asked": state.questions_asked,
            "last_coverage_check_turn": state.last_coverage_check_turn,
            "vignette_index": state.vignette_index,
            "vignette_replies": state.vignette_replies,
            "pending_artifact": state.pending_artifact,
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist dealbreaker answers to top-level columns as soon as we have them
    # (so they're queryable / editable independently of the JSONB sub_state).
    answers = state.dealbreaker_answers
    for col in (
        "gender_preference", "ethnicity_preference", "religion_preference",
        "relationship_intent", "partner_wants_kids", "partner_smokes_max",
        "partner_drinks_max", "partner_cannabis_max", "visual_importance",
    ):
        if col in answers:
            update_data[col] = answers[col]
    if "age_min" in answers:
        update_data["age_min"] = answers["age_min"]
    if "age_max" in answers:
        update_data["age_max"] = answers["age_max"]

    if turn.is_complete and turn.artifact:
        artifact = turn.artifact
        update_data["pull_pattern"] = artifact.get("pull_pattern")
        update_data["break_pattern"] = artifact.get("break_pattern")
        update_data["pull_pattern_quote"] = artifact.get("pull_pattern_quote")
        update_data["partner_traits"] = artifact.get("partner_traits") or []
        update_data["past_pulls"] = artifact.get("past_pulls") or []
        update_data["icks"] = artifact.get("icks") or []
        update_data["vignette_choices"] = artifact.get("vignette_choices") or []

    client.table("ideal_types").update(update_data).eq(
        "id", str(session.conversation_id)
    ).execute()

    if turn.is_complete:
        session.state = "ideal_type_complete"
        _save_session(session)

    return turn.reply
