"""Extract structured traits from a profiling conversation using Claude."""

from __future__ import annotations

import json
import logging
import re
from datetime import date

import anthropic

from kandal.core.config import get_settings
from kandal.profiling.prompts import (
    COVERAGE_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    TRAIT_DIMENSIONS,
    VALID_ATTACHMENT_STYLES,
    VALID_CONFLICT_STYLES,
    VALID_GENDERS,
    VALID_LOVE_LANGUAGES,
    VALID_RELATIONSHIP_HISTORIES,
)
from kandal.questionnaire.inference import InferredTraits

logger = logging.getLogger(__name__)

_MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_TIME_WORDS = {
    "early morning": "03:00-06:00", "dawn": "05:00-08:00",
    "morning": "06:00-09:00", "late morning": "09:00-12:00",
    "noon": "11:00-14:00", "midday": "11:00-14:00",
    "afternoon": "12:00-15:00", "late afternoon": "15:00-18:00",
    "evening": "18:00-21:00",
    "night": "21:00-00:00", "late night": "23:00-02:00",
    "midnight": "23:00-02:00",
}


def _normalize_birth_date(raw: str | None) -> str | None:
    """Best-effort normalization of a birth date string to ISO YYYY-MM-DD.

    Handles: "2000-03-28", "March 28, 2000", "28/03/2000", "03/28/2000",
    "Nov 28 2000", "YYYY-11-28" (malformed), "28 november 2000", etc.
    Returns None if unparseable or clearly invalid.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip()

    # Already valid ISO?
    try:
        date.fromisoformat(raw)
        return raw
    except ValueError:
        pass

    # Strip placeholder year markers
    if "YYYY" in raw.upper():
        return None  # year unknown — can't use

    # Try common patterns
    cleaned = raw.replace(",", " ").replace("/", " ").replace("-", " ").replace(".", " ")
    parts = cleaned.split()

    year, month, day = None, None, None

    for part in parts:
        part_lower = part.lower().strip()
        if part_lower in _MONTH_NAMES:
            month = _MONTH_NAMES[part_lower]
        elif part.isdigit():
            n = int(part)
            if n > 1900:
                year = n
            elif n > 31:
                year = n + 2000 if n < 100 else None
            elif month is None and day is None and n <= 12:
                # Ambiguous — could be month or day, defer
                if day is not None:
                    month = n
                else:
                    # First number: could be month (US) or day (EU)
                    day = n
            elif n <= 31:
                if day is None:
                    day = n
                elif month is None:
                    month = n

    # Handle case where we got day but no month yet, and remaining number fits as month
    # Re-scan for any missed digits
    if month is None or day is None or year is None:
        digits = [int(x) for x in re.findall(r"\d+", raw)]
        if len(digits) >= 3:
            # Try YYYY-MM-DD, DD-MM-YYYY, MM-DD-YYYY
            a, b, c = digits[0], digits[1], digits[2]
            if a > 1900:  # YYYY-MM-DD
                year, month, day = a, b, c
            elif c > 1900:  # DD-MM-YYYY or MM-DD-YYYY
                year = c
                if a > 12:  # must be DD-MM
                    day, month = a, b
                elif b > 12:  # must be MM-DD
                    month, day = a, b
                else:  # ambiguous, assume MM-DD (US)
                    month, day = a, b

    if year is None or month is None or day is None:
        return None

    try:
        d = date(year, month, day)
        return d.isoformat()
    except ValueError:
        # Try swapping month/day if out of range
        try:
            d = date(year, day, month)
            return d.isoformat()
        except ValueError:
            return None


def _normalize_birth_time(raw: str | None) -> str | None:
    """Normalize birth time to 'HH:00-HH:00' 3-hour window format.

    Handles: "06:00-09:00" (already valid), "morning", "5:38AM",
    "around 5am", "early morning", "between 3 and 6", etc.
    Returns None if unparseable.
    """
    if not raw or not isinstance(raw, str):
        return None

    raw = raw.strip().lower()

    # Already in HH:00-HH:00 format?
    if re.match(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", raw):
        return raw

    # Check word-based times
    for word, window in _TIME_WORDS.items():
        if word in raw:
            return window

    # Try to extract a specific hour: "5:38am", "5am", "around 5", "17:00"
    hour_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", raw)
    if hour_match:
        h = int(hour_match.group(1))
        ampm = hour_match.group(3)
        if ampm == "pm" and h < 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        if 0 <= h <= 23:
            # Build a 3-hour window centered on the hour
            start = max(0, h - 1)
            end = min(23, h + 2)
            return f"{start:02d}:00-{end:02d}:00"

    return None


def _get_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _format_conversation(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        role = "Kandal" if msg["role"] == "assistant" else "User"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from a response that may contain markdown code blocks."""
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())


def extract_traits(messages: list[dict]) -> tuple[InferredTraits, str]:
    """Extract InferredTraits + narrative from a completed conversation.

    Uses claude-sonnet-4-6 for accuracy on the final extraction.
    Returns (traits, narrative).
    """
    client = _get_client()
    conversation_text = _format_conversation(messages)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Here is the conversation:\n\n{conversation_text}"}
        ],
    )

    data = _parse_json_response(response.content[0].text)

    # Validate core traits
    attachment = data.get("attachment_style", "secure")
    if attachment not in VALID_ATTACHMENT_STYLES:
        attachment = "secure"

    conflict = data.get("conflict_style", "collaborative")
    if conflict not in VALID_CONFLICT_STYLES:
        conflict = "collaborative"

    history = data.get("relationship_history", "limited_experience")
    if history not in VALID_RELATIONSHIP_HISTORIES:
        history = "limited_experience"

    giving = data.get("love_language_giving", VALID_LOVE_LANGUAGES[:])
    giving = [l for l in giving if l in VALID_LOVE_LANGUAGES]
    for lang in VALID_LOVE_LANGUAGES:
        if lang not in giving:
            giving.append(lang)

    receiving = data.get("love_language_receiving", VALID_LOVE_LANGUAGES[:])
    receiving = [l for l in receiving if l in VALID_LOVE_LANGUAGES]
    for lang in VALID_LOVE_LANGUAGES:
        if lang not in receiving:
            receiving.append(lang)

    narrative = data.get("narrative", "")

    # Validate new fields
    gender_pref = data.get("gender_preference")
    if gender_pref is not None:
        gender_pref = [g for g in gender_pref if g in VALID_GENDERS]
        if not gender_pref:
            gender_pref = None

    cultural_prefs = data.get("cultural_preferences")
    if not isinstance(cultural_prefs, list):
        cultural_prefs = None

    birth_date = _normalize_birth_date(data.get("birth_date"))
    birth_time_approx = _normalize_birth_time(data.get("birth_time_approx"))
    birth_city = data.get("birth_city")

    # Validate dimension_weights: must be a dict with valid keys that sums to ~1.0
    dimension_weights = data.get("dimension_weights")
    if isinstance(dimension_weights, dict):
        from kandal.scoring.engine import DIMENSION_WEIGHTS
        valid_dims = set(DIMENSION_WEIGHTS.keys())
        # Keep only valid dimension keys with numeric values
        dimension_weights = {
            k: float(v) for k, v in dimension_weights.items()
            if k in valid_dims and isinstance(v, (int, float)) and v >= 0
        }
        # Normalize to sum to 1.0
        total = sum(dimension_weights.values())
        if total > 0 and dimension_weights:
            dimension_weights = {k: round(v / total, 4) for k, v in dimension_weights.items()}
            # Fill missing dimensions with 0
            for dim in valid_dims:
                if dim not in dimension_weights:
                    dimension_weights[dim] = 0.0
        else:
            dimension_weights = None
    else:
        dimension_weights = None

    traits = InferredTraits(
        attachment_style=attachment,
        love_language_giving=giving,
        love_language_receiving=receiving,
        conflict_style=conflict,
        relationship_history=history,
        gender_preference=gender_pref,
        cultural_preferences=cultural_prefs,
        birth_date=birth_date,
        birth_time_approx=birth_time_approx,
        birth_city=birth_city,
        dimension_weights=dimension_weights,
    )

    return traits, narrative


def assess_coverage(messages: list[dict]) -> dict[str, float]:
    """Estimate trait coverage confidence from conversation so far.

    Uses claude-haiku-4-5 for speed (called every few turns).
    Returns dict mapping dimension name to confidence 0-1.
    """
    if not messages:
        return {dim: 0.0 for dim in TRAIT_DIMENSIONS}

    client = _get_client()
    conversation_text = _format_conversation(messages)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=COVERAGE_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Conversation so far:\n\n{conversation_text}"}
        ],
    )

    try:
        data = _parse_json_response(response.content[0].text)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse coverage response")
        return {dim: 0.0 for dim in TRAIT_DIMENSIONS}

    coverage = {}
    for dim in TRAIT_DIMENSIONS:
        val = data.get(dim, 0.0)
        coverage[dim] = max(0.0, min(1.0, float(val)))

    return coverage
