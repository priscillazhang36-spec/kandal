"""State machine for SMS onboarding conversations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from kandal.core.config import get_settings
from kandal.core.supabase import get_supabase

logger = logging.getLogger(__name__)
from kandal.models.onboarding import OnboardingSession
from kandal.questionnaire import QUESTIONS, infer_traits
from kandal.sms import messages
from kandal.sms.service import send_sms

def _alert_admin(msg: str) -> None:
    """Send an SMS alert to the admin phone if configured."""
    try:
        admin_phone = get_settings().admin_phone
        if admin_phone:
            send_sms(admin_phone, f"[Kandal Alert] {msg}")
    except Exception as e:
        logger.error("Failed to send admin alert: %s", e)


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


def _finalize(session: OnboardingSession) -> bool:
    """Infer traits and save profile + preferences to DB.

    Returns True if core data (profile + preferences) saved successfully,
    False if something critical failed.
    """
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
    if traits.birth_date:
        # Validate it's a real date before saving to a DATE column
        try:
            from datetime import date as _date
            _date.fromisoformat(traits.birth_date)
            profile_update["birth_date"] = traits.birth_date
        except (ValueError, TypeError):
            logger.warning("Invalid birth_date from extraction: %s", traits.birth_date)
    if traits.birth_time_approx:
        profile_update["birth_time_approx"] = traits.birth_time_approx
    if traits.birth_city:
        profile_update["birth_city"] = traits.birth_city
    if traits.emotional_giving:
        profile_update["emotional_giving"] = traits.emotional_giving
    if traits.emotional_needs:
        profile_update["emotional_needs"] = traits.emotional_needs

    try:
        client.table("profiles").update(profile_update).eq(
            "id", str(session.profile_id)
        ).execute()
    except Exception as e:
        logger.error("Failed to save profile for %s: %s", session.phone, e)
        _alert_admin(f"Profile save failed for {session.phone}: {e}")
        return False

    # Gender preference: conversation-extracted takes priority, basics-collected as fallback
    gender_pref = traits.gender_preference or session.collected_basics.get("gender_preference")

    prefs_data = {
        "profile_id": str(session.profile_id),
        "attachment_style": traits.attachment_style,
        "love_language_giving": traits.love_language_giving,
        "love_language_receiving": traits.love_language_receiving,
        "conflict_style": traits.conflict_style,
        "relationship_history": traits.relationship_history,
    }
    if gender_pref:
        prefs_data["gender_preferences"] = gender_pref
    if traits.cultural_preferences:
        prefs_data["cultural_preferences"] = traits.cultural_preferences
    if traits.dimension_weights:
        prefs_data["dimension_weights"] = traits.dimension_weights

    try:
        client.table("preferences").upsert(
            prefs_data,
            on_conflict="profile_id",
        ).execute()
    except Exception as e:
        logger.error("Failed to save preferences for %s: %s", session.phone, e)
        _alert_admin(f"Preferences save failed for {session.phone}: {e}")
        return False

    # Generate and store embeddings (non-critical)
    try:
        from kandal.profiling.embeddings import (
            embed_emotional_dynamics,
            embed_narrative,
            store_narrative_and_embedding,
        )

        if narrative:
            embedding = embed_narrative(narrative)
            store_narrative_and_embedding(session.profile_id, narrative, embedding)

        if traits.emotional_giving or traits.emotional_needs:
            giving_emb, needs_emb = embed_emotional_dynamics(
                traits.emotional_giving, traits.emotional_needs
            )
            emb_update = {}
            if giving_emb:
                emb_update["emotional_giving_embedding"] = giving_emb
            if needs_emb:
                emb_update["emotional_needs_embedding"] = needs_emb
            if emb_update:
                client.table("profiles").update(emb_update).eq(
                    "id", str(session.profile_id)
                ).execute()
    except Exception as e:
        logger.warning("Failed to generate embeddings: %s", e)

    return True


def _prefill_basics_from_traits(session: OnboardingSession) -> None:
    """Pre-fill collected_basics from profiling conversation traits to avoid re-asking."""
    client = get_supabase()

    if not session.conversation_id:
        return

    conv_resp = (
        client.table("profiling_conversations")
        .select("extracted_traits")
        .eq("id", str(session.conversation_id))
        .execute()
    )
    if not conv_resp.data or not conv_resp.data[0].get("extracted_traits"):
        return

    traits = conv_resp.data[0]["extracted_traits"]

    # Age from birth_date
    if traits.get("birth_date") and "age" not in session.collected_basics:
        try:
            from datetime import date as _date
            bd = _date.fromisoformat(traits["birth_date"])
            today = _date.today()
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            if 18 <= age <= 99:
                session.collected_basics["age"] = age
        except (ValueError, TypeError):
            pass

    # Gender preference
    if traits.get("gender_preference") and "gender_preference" not in session.collected_basics:
        session.collected_basics["gender_preference"] = traits["gender_preference"]


def _next_missing_basic(session: OnboardingSession) -> tuple[str, str]:
    """Return (next_state, prompt) for the first missing basic field."""
    basics = session.collected_basics

    if "name" not in basics:
        return "collecting_name", messages.BASICS_INTRO
    if "age" not in basics:
        return "collecting_age", messages.BASICS_AGE
    if "gender" not in basics:
        return "collecting_gender", messages.BASICS_GENDER
    if "gender_preference" not in basics:
        return "collecting_gender_preference", messages.BASICS_GENDER_PREFERENCE
    if "city" not in basics:
        return "collecting_city", messages.BASICS_CITY

    # Everything collected — finalize directly
    return "complete", ""


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

        conv_status = conv.get("status", "in_progress")
        state = ProfilingState(
            profile_id=UUID(str(session.profile_id)),
            messages=conv["messages"],
            coverage=conv.get("coverage", {}),
            questions_asked=len([m for m in conv["messages"] if m["role"] == "assistant"]),
            awaiting_confirmation=(conv_status == "awaiting_confirmation"),
            awaiting_ranking=(conv_status == "awaiting_ranking"),
            pending_traits=conv.get("extracted_traits"),
            pending_narrative=conv.get("narrative"),
        )

        engine = ProfilingEngine()
        turn = engine.next_turn(state, body)

        # Save updated conversation
        update_data = {
            "messages": state.messages,
            "coverage": turn.coverage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if turn.awaiting_ranking:
            update_data["status"] = "awaiting_ranking"
            if turn.traits:
                update_data["extracted_traits"] = turn.traits.model_dump()
            if turn.narrative:
                update_data["narrative"] = turn.narrative
        elif turn.awaiting_confirmation:
            update_data["status"] = "awaiting_confirmation"
            if turn.traits:
                update_data["extracted_traits"] = turn.traits.model_dump()
            if turn.narrative:
                update_data["narrative"] = turn.narrative
        elif turn.is_complete:
            update_data["status"] = "complete"
            if turn.traits:
                update_data["extracted_traits"] = turn.traits.model_dump()
            if turn.narrative:
                update_data["narrative"] = turn.narrative

        client.table("profiling_conversations").update(update_data).eq(
            "id", str(session.conversation_id)
        ).execute()

        if turn.is_complete:
            # Pre-fill basics from extracted traits to avoid re-asking
            _prefill_basics_from_traits(session)
            next_state, next_prompt = _next_missing_basic(session)
            session.state = next_state
            _save_session(session)
            if next_state == "complete":
                if _finalize(session):
                    return f"{turn.reply}\n\n{messages.ONBOARDING_COMPLETE}"
                session.state = "finalize_failed"
                _save_session(session)
                return f"{turn.reply}\n\n{messages.FINALIZE_FAILED}"
            return f"{turn.reply}\n\n{next_prompt}"

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
    next_state, next_prompt = _next_missing_basic(session)
    session.state = next_state
    _save_session(session)
    if next_state == "complete":
        if _finalize(session):
            return messages.ONBOARDING_COMPLETE
        session.state = "finalize_failed"
        _save_session(session)
        return messages.FINALIZE_FAILED
    return next_prompt


def _handle_collecting_age(session: OnboardingSession, body: str) -> str:
    cleaned = body.strip()
    try:
        age = int(cleaned)
    except ValueError:
        return messages.BASICS_AGE_INVALID

    if age < 18 or age > 99:
        return messages.BASICS_AGE_INVALID

    session.collected_basics["age"] = age
    next_state, next_prompt = _next_missing_basic(session)
    session.state = next_state
    _save_session(session)
    if next_state == "complete":
        if _finalize(session):
            return messages.ONBOARDING_COMPLETE
        session.state = "finalize_failed"
        _save_session(session)
        return messages.FINALIZE_FAILED
    return next_prompt


def _handle_collecting_gender(session: OnboardingSession, body: str) -> str:
    cleaned = body.strip().lower()
    if cleaned not in VALID_GENDERS:
        return messages.BASICS_GENDER_INVALID

    session.collected_basics["gender"] = cleaned
    next_state, next_prompt = _next_missing_basic(session)
    session.state = next_state
    _save_session(session)
    if next_state == "complete":
        if _finalize(session):
            return messages.ONBOARDING_COMPLETE
        session.state = "finalize_failed"
        _save_session(session)
        return messages.FINALIZE_FAILED
    return next_prompt


def _parse_gender_preference(text: str) -> list[str] | None:
    """Parse free-text gender preference into a list of valid genders."""
    cleaned = text.strip().lower()
    # Handle common shortcuts
    if cleaned in ("both", "everyone", "all", "any", "no preference"):
        return ["male", "female", "nonbinary"]
    found = [g for g in VALID_GENDERS if g in cleaned]
    return found if found else None


def _handle_collecting_gender_preference(session: OnboardingSession, body: str) -> str:
    prefs = _parse_gender_preference(body)
    if prefs is None:
        return messages.BASICS_GENDER_PREFERENCE_INVALID

    session.collected_basics["gender_preference"] = prefs
    next_state, next_prompt = _next_missing_basic(session)
    session.state = next_state
    _save_session(session)
    if next_state == "complete":
        if _finalize(session):
            return messages.ONBOARDING_COMPLETE
        session.state = "finalize_failed"
        _save_session(session)
        return messages.FINALIZE_FAILED
    return next_prompt


def _handle_collecting_city(session: OnboardingSession, body: str) -> str:
    city = body.strip()
    if not city:
        return "What city are you in?"

    session.collected_basics["city"] = city
    session.state = "complete"
    _save_session(session)
    if _finalize(session):
        return messages.ONBOARDING_COMPLETE
    else:
        session.state = "finalize_failed"
        _save_session(session)
        return messages.FINALIZE_FAILED


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
