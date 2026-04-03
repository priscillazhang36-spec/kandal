"""State machine for SMS onboarding conversations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from kandal.core.supabase import get_supabase

logger = logging.getLogger(__name__)
from kandal.models.onboarding import OnboardingSession
from kandal.questionnaire import QUESTIONS, infer_traits
from kandal.sms import messages
from kandal.sms.service import send_sms

LETTER_MAP = {"a": 0, "b": 1, "c": 2, "d": 3}
VALID_GENDERS = {"male", "female", "nonbinary"}


def _parse_answer(text: str) -> int | None:
    cleaned = text.strip().lower()
    if cleaned in LETTER_MAP:
        return LETTER_MAP[cleaned]
    if cleaned in ("1", "2", "3", "4"):
        return int(cleaned) - 1
    return None


def _load_session(phone: str) -> OnboardingSession | None:
    client = get_supabase()
    resp = client.table("onboarding_sessions").select("*").eq("phone", phone).execute()
    if not resp.data:
        return None
    return OnboardingSession(**resp.data[0])


def _save_session(session: OnboardingSession) -> None:
    client = get_supabase()
    data = session.model_dump(mode="json")
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    client.table("onboarding_sessions").update(data).eq("id", str(session.id)).execute()


def _finalize(session: OnboardingSession) -> None:
    """Infer traits (from adaptive profiling or fixed questionnaire), update profile, create preferences."""
    client = get_supabase()

    # Check if we have adaptive profiling results
    narrative = None
    if session.conversation_id:
        conv_resp = (
            client.table("profiling_conversations")
            .select("extracted_traits, narrative")
            .eq("id", str(session.conversation_id))
            .execute()
        )
        if conv_resp.data and conv_resp.data[0].get("extracted_traits"):
            from kandal.questionnaire.inference import InferredTraits

            traits = InferredTraits(**conv_resp.data[0]["extracted_traits"])
            narrative = conv_resp.data[0].get("narrative")
        else:
            # Fallback to fixed questionnaire inference
            traits = infer_traits(session.answers)
    else:
        traits = infer_traits(session.answers)

    profile_update = {
        "name": session.collected_basics["name"],
        "age": session.collected_basics["age"],
        "gender": session.collected_basics["gender"],
        "city": session.collected_basics["city"],
        "is_active": True,
    }
    if narrative:
        profile_update["narrative"] = narrative

    client.table("profiles").update(profile_update).eq(
        "id", str(session.profile_id)
    ).execute()

    client.table("preferences").upsert(
        {
            "profile_id": str(session.profile_id),
            "attachment_style": traits.attachment_style,
            "love_language_giving": traits.love_language_giving,
            "love_language_receiving": traits.love_language_receiving,
            "conflict_style": traits.conflict_style,
            "relationship_history": traits.relationship_history,
        },
        on_conflict="profile_id",
    ).execute()

    # Generate and store embedding if we have a narrative
    if narrative:
        try:
            from kandal.profiling.embeddings import embed_narrative, store_narrative_and_embedding

            embedding = embed_narrative(narrative)
            store_narrative_and_embedding(session.profile_id, narrative, embedding)
        except Exception as e:
            logger.warning("Failed to generate embedding: %s", e)


def _handle_awaiting_code(session: OnboardingSession, body: str) -> str:
    # Check expiry
    if session.code_expires_at and datetime.now(timezone.utc) > session.code_expires_at:
        session.state = "expired"
        _save_session(session)
        return messages.CODE_TIMED_OUT

    if body.strip() == session.verification_code:
        # Create profile row with just the phone
        client = get_supabase()
        resp = client.table("profiles").insert({
            "phone": session.phone,
            "is_active": False,
        }).execute()
        session.profile_id = resp.data[0]["id"]

        # Try adaptive profiling, fall back to fixed questions
        try:
            from kandal.profiling.engine import ProfilingEngine

            engine = ProfilingEngine()
            state, opening = engine.start(UUID(session.profile_id))

            # Save conversation to DB
            conv_resp = client.table("profiling_conversations").insert({
                "profile_id": session.profile_id,
                "messages": state.messages,
                "coverage": state.coverage,
                "status": "in_progress",
            }).execute()

            session.conversation_id = conv_resp.data[0]["id"]
            session.state = "adaptive_profiling"
            _save_session(session)
            return opening
        except Exception as e:
            logger.warning("Adaptive profiling unavailable, falling back to fixed questions: %s", e)
            session.state = "onboarding_q1"
            _save_session(session)
            q_text = messages.format_question(QUESTIONS[0])
            return f"{messages.QUESTION_INTRO}\n\n{q_text}"

    # Wrong code
    session.code_attempts += 1
    if session.code_attempts >= 3:
        session.state = "expired"
        _save_session(session)
        return messages.CODE_EXPIRED

    _save_session(session)
    return messages.CODE_WRONG.format(attempts=session.code_attempts)


def _handle_adaptive_profiling(session: OnboardingSession, body: str) -> str:
    """Handle a message during adaptive profiling conversation."""
    client = get_supabase()

    # Load conversation state
    conv_resp = (
        client.table("profiling_conversations")
        .select("*")
        .eq("id", str(session.conversation_id))
        .execute()
    )
    if not conv_resp.data:
        # Conversation lost — fall back to fixed questions
        session.state = "onboarding_q1"
        _save_session(session)
        q_text = messages.format_question(QUESTIONS[0])
        return f"{messages.QUESTION_INTRO}\n\n{q_text}"

    conv = conv_resp.data[0]

    try:
        from kandal.profiling.engine import ProfilingEngine, ProfilingState

        state = ProfilingState(
            profile_id=UUID(str(session.profile_id)),
            messages=conv["messages"],
            coverage=conv.get("coverage", {}),
            questions_asked=len([m for m in conv["messages"] if m["role"] == "assistant"]),
        )

        engine = ProfilingEngine()
        turn = engine.next_turn(state, body)

        # Save updated conversation
        update_data = {
            "messages": state.messages,
            "coverage": turn.coverage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if turn.is_complete:
            update_data["status"] = "complete"
            if turn.traits:
                update_data["extracted_traits"] = turn.traits.model_dump()
            if turn.narrative:
                update_data["narrative"] = turn.narrative

        client.table("profiling_conversations").update(update_data).eq(
            "id", str(session.conversation_id)
        ).execute()

        if turn.is_complete:
            session.state = "collecting_name"
            _save_session(session)
            return f"{turn.reply}\n\n{messages.BASICS_INTRO}"

        _save_session(session)
        return turn.reply

    except Exception as e:
        logger.warning("Adaptive profiling failed mid-conversation: %s", e)
        # Fall back to fixed questions from the beginning
        session.state = "onboarding_q1"
        session.conversation_id = None
        _save_session(session)
        q_text = messages.format_question(QUESTIONS[0])
        return f"{messages.QUESTION_INTRO}\n\n{q_text}"


def _handle_question(session: OnboardingSession, body: str, q_index: int) -> str:
    answer = _parse_answer(body)
    if answer is None:
        return messages.ANSWER_NOT_UNDERSTOOD

    session.answers.append(answer)

    if q_index < 9:
        # Next question
        session.state = f"onboarding_q{q_index + 2}"
        _save_session(session)
        transition = messages.transition_phrase()
        q_text = messages.format_question(QUESTIONS[q_index + 1])
        prefix = f"{transition}\n\n" if transition else ""
        return f"{prefix}{q_text}"
    else:
        # Last question answered — move to basics
        session.state = "collecting_name"
        _save_session(session)
        return messages.BASICS_INTRO


def _handle_collecting_name(session: OnboardingSession, body: str) -> str:
    name = body.strip()
    if not name:
        return "I need a name! What should I call you?"
    session.collected_basics["name"] = name
    session.state = "collecting_age"
    _save_session(session)
    return messages.BASICS_AGE


def _handle_collecting_age(session: OnboardingSession, body: str) -> str:
    cleaned = body.strip()
    try:
        age = int(cleaned)
    except ValueError:
        return messages.BASICS_AGE_INVALID

    if age < 18 or age > 99:
        return messages.BASICS_AGE_INVALID

    session.collected_basics["age"] = age
    session.state = "collecting_gender"
    _save_session(session)
    return messages.BASICS_GENDER


def _handle_collecting_gender(session: OnboardingSession, body: str) -> str:
    cleaned = body.strip().lower()
    if cleaned not in VALID_GENDERS:
        return messages.BASICS_GENDER_INVALID

    session.collected_basics["gender"] = cleaned
    session.state = "collecting_city"
    _save_session(session)
    return messages.BASICS_CITY


def _handle_collecting_city(session: OnboardingSession, body: str) -> str:
    city = body.strip()
    if not city:
        return "What city are you in?"

    session.collected_basics["city"] = city
    session.state = "complete"
    _save_session(session)
    _finalize(session)
    return messages.ONBOARDING_COMPLETE


def route_message(phone: str, body: str) -> str:
    """Main entry point. Load session, dispatch to handler, send reply."""
    session = _load_session(phone)

    if session is None:
        return messages.RESTART_HINT

    state = session.state

    if state == "awaiting_code":
        reply = _handle_awaiting_code(session, body)
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
    elif state == "collecting_city":
        reply = _handle_collecting_city(session, body)
    elif state == "complete":
        reply = messages.ALREADY_COMPLETE
    elif state == "expired":
        reply = messages.SESSION_EXPIRED
    else:
        reply = messages.RESTART_HINT

    logger.info("phone=%s state=%s body=%r reply=%r", phone, state, body, reply[:80])
    try:
        send_sms(phone, reply)
    except Exception as e:
        logger.error("send_sms failed: %s", e)
    return reply
