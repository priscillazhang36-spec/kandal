from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response

from kandal.core.supabase import get_supabase
from kandal.schemas.auth import PhoneAuthRequest
from kandal.sms import messages
from kandal.sms.handler import route_message
from kandal.sms.service import generate_verification_code, code_expiry, send_sms

router = APIRouter()

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response/>'


@router.post("/auth/start")
def start_phone_auth(body: PhoneAuthRequest):
    """Send a verification code via SMS. Creates or resets an onboarding session."""
    client = get_supabase()

    # Rate limit: 60s cooldown per phone
    existing = (
        client.table("onboarding_sessions")
        .select("created_at")
        .eq("phone", body.phone)
        .execute()
    )
    if existing.data:
        created = datetime.fromisoformat(existing.data[0]["created_at"])
        if datetime.now(timezone.utc) - created < timedelta(seconds=60):
            raise HTTPException(429, "Please wait before requesting another code.")

    code = generate_verification_code()
    expires = code_expiry()

    # Upsert session (reset if exists)
    client.table("onboarding_sessions").upsert(
        {
            "phone": body.phone,
            "state": "awaiting_code",
            "verification_code": code,
            "code_expires_at": expires.isoformat(),
            "code_attempts": 0,
            "profile_id": None,
            "answers": [],
            "collected_basics": {},
        },
        on_conflict="phone",
    ).execute()

    send_sms(body.phone, messages.WELCOME)
    return {"status": "code_sent"}


@router.post("/sms/webhook")
async def twilio_webhook(request: Request):
    """Twilio POSTs incoming SMS here. Routes through state machine, returns empty TwiML."""
    form = await request.form()
    phone = form.get("From", "")
    body = form.get("Body", "")

    if not phone:
        return Response(content=EMPTY_TWIML, media_type="text/xml")

    # Handle "START" as a new session trigger
    if body.strip().upper() == "START":
        start_phone_auth(PhoneAuthRequest(phone=phone))
        return Response(content=EMPTY_TWIML, media_type="text/xml")

    route_message(phone, body)
    return Response(content=EMPTY_TWIML, media_type="text/xml")
