import logging
from datetime import datetime, timedelta, timezone

import sentry_sdk
from fastapi import APIRouter, HTTPException, Request, Response

logger = logging.getLogger(__name__)

from kandal.core.supabase import get_supabase
from kandal.schemas.auth import PhoneAuthRequest
from kandal.sms import messages
from kandal.sms.handler import route_message
from kandal.sms.service import send_sms

router = APIRouter()

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response/>'


@router.post("/auth/start")
def start_phone_auth(body: PhoneAuthRequest):
    """Start onboarding via SMS. Creates profile and begins profiling conversation."""
    client = get_supabase()

    # Rate limit: 60s cooldown per phone
    existing = (
        client.table("onboarding_sessions")
        .select("created_at, state")
        .eq("phone", body.phone)
        .execute()
    )
    if existing.data:
        created = datetime.fromisoformat(existing.data[0]["created_at"])
        if datetime.now(timezone.utc) - created < timedelta(seconds=60):
            raise HTTPException(429, "Please wait before requesting again.")

    # Create or find profile
    profile_resp = client.table("profiles").select("id").eq("phone", body.phone).execute()
    if profile_resp.data:
        profile_id = profile_resp.data[0]["id"]
    else:
        resp = client.table("profiles").insert({"phone": body.phone, "is_active": False}).execute()
        profile_id = resp.data[0]["id"]

    # Try adaptive profiling, fall back to fixed questions
    try:
        from uuid import UUID
        from kandal.profiling.engine import ProfilingEngine

        engine = ProfilingEngine()
        state, opening = engine.start(UUID(str(profile_id)))

        conv_resp = client.table("profiling_conversations").insert({
            "profile_id": str(profile_id),
            "messages": state.messages,
            "coverage": state.coverage,
            "status": "in_progress",
        }).execute()

        client.table("onboarding_sessions").upsert(
            {
                "phone": body.phone,
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

        send_sms(body.phone, opening)
    except Exception as e:
        logger.error("Adaptive profiling unavailable, falling back to fixed questions: %s", e)
        sentry_sdk.capture_exception(e)

        client.table("onboarding_sessions").upsert(
            {
                "phone": body.phone,
                "state": "onboarding_q1",
                "verification_code": None,
                "code_expires_at": None,
                "code_attempts": 0,
                "profile_id": str(profile_id),
                "answers": [],
                "collected_basics": {},
            },
            on_conflict="phone",
        ).execute()

        from kandal.questionnaire import QUESTIONS
        q_text = messages.format_question(QUESTIONS[0])
        send_sms(body.phone, f"Hey! Welcome to Kandal.\n\n{messages.QUESTION_INTRO}\n\n{q_text}")

    return {"status": "started"}


@router.post("/sms/webhook")
async def twilio_webhook(request: Request):
    """Twilio POSTs incoming SMS here. Routes through state machine, returns empty TwiML."""
    form = await request.form()
    phone = form.get("From", "")
    body = form.get("Body", "")

    if not phone:
        return Response(content=EMPTY_TWIML, media_type="text/xml")

    logger.info("Webhook: phone=%s body=%r", phone, body)

    logger.info("Webhook: phone=%s body=%r", phone, body)

    # Handle "START" as a new session trigger — skip verification, go straight to profiling
    if body.strip().upper() == "START":
        try:
            client = get_supabase()
            existing = client.table("profiles").select("id").eq("phone", phone).execute()
            if existing.data:
                profile_id = existing.data[0]["id"]
            else:
                resp = client.table("profiles").insert({"phone": phone, "is_active": False}).execute()
                profile_id = resp.data[0]["id"]

            # Try adaptive profiling first
            try:
                from uuid import UUID
                from kandal.profiling.engine import ProfilingEngine

                engine = ProfilingEngine()
                state, opening = engine.start(UUID(str(profile_id)))

                conv_resp = client.table("profiling_conversations").insert({
                    "profile_id": str(profile_id),
                    "messages": state.messages,
                    "coverage": state.coverage,
                    "status": "in_progress",
                }).execute()

                client.table("onboarding_sessions").upsert(
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

                send_sms(phone, opening)
            except Exception as e:
                logger.warning("Adaptive profiling unavailable, falling back to fixed questions: %s", e)
                client.table("onboarding_sessions").upsert(
                    {
                        "phone": phone,
                        "state": "onboarding_q1",
                        "verification_code": None,
                        "code_expires_at": None,
                        "code_attempts": 0,
                        "profile_id": str(profile_id),
                        "answers": [],
                        "collected_basics": {},
                    },
                    on_conflict="phone",
                ).execute()

                from kandal.questionnaire import QUESTIONS
                q_text = messages.format_question(QUESTIONS[0])
                send_sms(phone, f"{messages.QUESTION_INTRO}\n\n{q_text}")
        except Exception as e:
            logger.error("START handler failed: %s", e, exc_info=True)
            return Response(content=f"error: {e}", media_type="text/plain", status_code=500)
        return Response(content=EMPTY_TWIML, media_type="text/xml")

    try:
        route_message(phone, body)
    except Exception as e:
        logger.error("route_message failed: %s", e, exc_info=True)
        return Response(content=f"error: {e}", media_type="text/plain", status_code=500)
    return Response(content=EMPTY_TWIML, media_type="text/xml")
