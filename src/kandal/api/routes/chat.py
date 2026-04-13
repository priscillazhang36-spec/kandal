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
    """Start a web chat profiling session. Returns opening message."""
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

    # Start adaptive profiling
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

    if state == "adaptive_profiling":
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
    elif state == "expired":
        reply = messages.SESSION_EXPIRED
    else:
        reply = messages.RESTART_HINT

    logger.info("web_chat phone=%s state=%s body=%r reply=%r", phone, state, body, reply[:80])
    return reply
