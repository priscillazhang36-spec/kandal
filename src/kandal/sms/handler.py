"""State machine for SMS onboarding conversations."""

from datetime import datetime, timezone

from kandal.core.supabase import get_supabase
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
    """Infer traits, update profile with basics, create preferences."""
    traits = infer_traits(session.answers)
    client = get_supabase()

    client.table("profiles").update({
        "name": session.collected_basics["name"],
        "age": session.collected_basics["age"],
        "gender": session.collected_basics["gender"],
        "city": session.collected_basics["city"],
        "is_active": True,
    }).eq("id", str(session.profile_id)).execute()

    client.table("preferences").upsert({
        "profile_id": str(session.profile_id),
        "attachment_style": traits.attachment_style,
        "love_language_giving": traits.love_language_giving,
        "love_language_receiving": traits.love_language_receiving,
        "conflict_style": traits.conflict_style,
        "relationship_history": traits.relationship_history,
    }, on_conflict="profile_id").execute()


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

    send_sms(phone, reply)
    return reply
