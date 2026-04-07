"""Centralized error alerting: Sentry + SMS fallback."""

from __future__ import annotations

import logging
from typing import Optional

import sentry_sdk

logger = logging.getLogger(__name__)


def capture_error(error: Exception, context: Optional[dict] = None) -> None:
    """Send an exception to Sentry with optional context."""
    if context:
        sentry_sdk.set_context("extra", context)
    sentry_sdk.capture_exception(error)


def critical_alert(message: str, error: Optional[Exception] = None) -> None:
    """Capture in Sentry and send SMS to admin. Never raises."""
    try:
        if error:
            sentry_sdk.set_context("alert", {"message": message})
            sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_message(message, level="error")

        from kandal.core.config import get_settings
        from kandal.sms.service import send_sms

        admin_phone = get_settings().admin_phone
        if admin_phone:
            send_sms(admin_phone, f"[Kandal Alert] {message}")
    except Exception as sms_err:
        logger.error("critical_alert failed to send SMS: %s", sms_err)
        sentry_sdk.capture_exception(sms_err)
