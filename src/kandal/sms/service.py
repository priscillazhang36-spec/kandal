"""Twilio SMS wrapper."""

import secrets
from datetime import datetime, timedelta, timezone

from twilio.rest import Client as TwilioClient

from kandal.core.config import get_settings


def get_twilio_client() -> TwilioClient:
    s = get_settings()
    return TwilioClient(s.twilio_account_sid, s.twilio_auth_token)


def send_sms(to: str, body: str) -> None:
    s = get_settings()
    client = get_twilio_client()
    client.messages.create(
        body=body,
        from_=s.twilio_phone_number,
        to=to,
    )


def generate_verification_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def code_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=10)
