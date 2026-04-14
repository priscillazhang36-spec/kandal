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


# Behavioral phrases that indicate *real* love-language evidence (user-side only).
# If none appear in the user's messages, the LLM's LL inference is hallucination.
_LL_BEHAVIOR_PHRASES = (
    "words of affirmation", "quality time", "physical touch", "acts of service",
    # Words-of-affirmation signals — concrete phrases only
    "compliment", "tell me he loves", "tell me she loves", "tell me they love",
    "hear him say", "hear her say", "hear them say", "verbal affirmation",
    "encouraging words", "kind words",
    # Quality-time signals — concrete phrases only
    "spend time together", "undivided attention", "phone away", "one-on-one time",
    "date night",
    # Physical-touch signals — concrete phrases only
    "hold hands", "cuddle", "hug me", "hugs", "kissing", "physical affection",
    "sit close", "back rub",
    # Acts-of-service signals — concrete phrases only
    "do things for me", "takes care of", "plan things for me", "plans things for me",
    "cooks for me", "helps me with chores", "takes something off my plate",
    "makes me dinner", "brings me coffee", "runs errands",
    # Gift signals — concrete phrases only
    "brings me flowers", "surprise me with", "thoughtful gift", "thoughtful present",
    "thoughtful gifts",
)


_ATTACHMENT_PHRASES = (
    "anxious", "clingy", "needy", "pull away", "pulled away", "distance myself",
    "overthink", "avoidant", "avoid commitment", "secure", "insecure", "abandon",
    "worry they", "worry he", "worry she", "push people away", "shut down emotionally",
    "attachment",
)

_CONFLICT_PHRASES = (
    "when we fight", "arguments", "argue", "disagreement", "shut down",
    "need space", "cool off", "cool down", "talk it out", "avoid confrontation",
    "avoid conflict", "stonewall", "silent treatment", "blow up", "yell",
    "walk away", "address it immediately", "hash it out",
)

_HISTORY_PHRASES = (
    "my ex", "past relationship", "last relationship", "long-term", "long term",
    "serious relationship", "never really dated", "never dated",
    "casual", "situationship", "just out of", "break up", "broke up",
    "got out of", "single for", "haven't dated", "haven't been dating",
    "dated someone", "years with", "years together",
)


def _user_text(messages: list[dict]) -> str:
    return " ".join(
        m["content"].lower()
        for m in messages
        if m.get("role") == "user" and isinstance(m.get("content"), str)
    )


def _user_mentioned_love_behaviors(messages: list[dict]) -> bool:
    text = _user_text(messages)
    return any(p in text for p in _LL_BEHAVIOR_PHRASES)


def _has_phrase(messages: list[dict], phrases: tuple[str, ...]) -> bool:
    text = _user_text(messages)
    return any(p in text for p in phrases)


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from a response that may contain markdown code blocks."""
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())


def extract_traits(messages: list[dict]) -> tuple[InferredTraits, str, set[str]]:
    """Extract InferredTraits + narrative from a completed conversation.

    Returns (traits, narrative, low_confidence_fields). The third element names
    fields that were defaulted because the conversation provided no real signal.
    Callers (e.g. the summary step) should skip these to avoid stating fallbacks
    as facts.
    """
    client = _get_client()
    conversation_text = _format_conversation(messages)

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Here is the conversation:\n\n{conversation_text}"}
        ],
    )

    data = _parse_json_response(response.content[0].text)
    low_conf: set[str] = set()

    # Defensive check: if user never used love-behavior language, force LL to low_conf
    # regardless of what the extractor LLM returned. Haiku sometimes infers LL from
    # personality MCQs despite the prompt forbidding it — this is the safety net.
    ll_behaviors_present = _user_mentioned_love_behaviors(messages)

    # Validate core traits — track which were defaulted vs signaled
    raw_attachment = data.get("attachment_style")
    if raw_attachment in VALID_ATTACHMENT_STYLES and _has_phrase(messages, _ATTACHMENT_PHRASES):
        attachment = raw_attachment
    else:
        attachment = "secure"
        low_conf.add("attachment_style")

    raw_conflict = data.get("conflict_style")
    if raw_conflict in VALID_CONFLICT_STYLES and _has_phrase(messages, _CONFLICT_PHRASES):
        conflict = raw_conflict
    else:
        conflict = "collaborative"
        low_conf.add("conflict_style")

    raw_history = data.get("relationship_history")
    if raw_history in VALID_RELATIONSHIP_HISTORIES and _has_phrase(messages, _HISTORY_PHRASES):
        history = raw_history
    else:
        history = "limited_experience"
        low_conf.add("relationship_history")

    raw_giving = data.get("love_language_giving")
    if (
        ll_behaviors_present
        and isinstance(raw_giving, list)
        and any(l in VALID_LOVE_LANGUAGES for l in raw_giving)
    ):
        giving = [l for l in raw_giving if l in VALID_LOVE_LANGUAGES]
        for lang in VALID_LOVE_LANGUAGES:
            if lang not in giving:
                giving.append(lang)
    else:
        giving = VALID_LOVE_LANGUAGES[:]
        low_conf.add("love_language_giving")

    raw_receiving = data.get("love_language_receiving")
    if (
        ll_behaviors_present
        and isinstance(raw_receiving, list)
        and any(l in VALID_LOVE_LANGUAGES for l in raw_receiving)
    ):
        receiving = [l for l in raw_receiving if l in VALID_LOVE_LANGUAGES]
        for lang in VALID_LOVE_LANGUAGES:
            if lang not in receiving:
                receiving.append(lang)
    else:
        receiving = VALID_LOVE_LANGUAGES[:]
        low_conf.add("love_language_receiving")

    narrative = data.get("narrative", "")

    # Basic info
    extracted_name = data.get("name")
    if not isinstance(extracted_name, str) or not extracted_name.strip():
        extracted_name = None

    extracted_gender = data.get("gender")
    if extracted_gender not in VALID_GENDERS:
        extracted_gender = None

    current_city = data.get("current_city")
    if not isinstance(current_city, str) or not current_city.strip():
        current_city = None

    # Validate new fields
    gender_pref = data.get("gender_preference")
    if gender_pref is not None:
        if not isinstance(gender_pref, list):
            gender_pref = None
        else:
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

    # Emotional dynamics — the core matching signal
    emotional_giving = data.get("emotional_giving")
    if not isinstance(emotional_giving, str) or len(emotional_giving.strip()) < 10:
        emotional_giving = None

    emotional_needs = data.get("emotional_needs")
    if not isinstance(emotional_needs, str) or len(emotional_needs.strip()) < 10:
        emotional_needs = None

    # Tier 1 tag lists — validate as lists of strings
    interests = data.get("interests")
    if not isinstance(interests, list):
        interests = None
    else:
        interests = [str(t).lower().strip() for t in interests if isinstance(t, str)]
        interests = interests or None

    personality = data.get("personality")
    if not isinstance(personality, list):
        personality = None
    else:
        personality = [str(t).lower().strip() for t in personality if isinstance(t, str)]
        personality = personality or None

    partner_personality = data.get("partner_personality")
    if not isinstance(partner_personality, list):
        partner_personality = None
    else:
        partner_personality = [str(t).lower().strip() for t in partner_personality if isinstance(t, str)]
        partner_personality = partner_personality or None

    values = data.get("values")
    if not isinstance(values, list):
        values = None
    else:
        values = [str(t).lower().strip() for t in values if isinstance(t, str)]
        values = values or None

    partner_values = data.get("partner_values")
    if not isinstance(partner_values, list):
        partner_values = None
    else:
        partner_values = [str(t).lower().strip() for t in partner_values if isinstance(t, str)]
        partner_values = partner_values or None

    lifestyle = data.get("lifestyle")
    if not isinstance(lifestyle, list):
        lifestyle = None
    else:
        lifestyle = [str(t).lower().strip() for t in lifestyle if isinstance(t, str)]
        lifestyle = lifestyle or None

    def _enum(key: str, allowed: set[str]) -> str | None:
        v = data.get(key)
        return v if isinstance(v, str) and v in allowed else None

    def _int(key: str) -> int | None:
        v = data.get(key)
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    age_min = _int("age_min")
    age_max = _int("age_max")
    max_distance_km = _int("max_distance_km")
    relationship_intent = _enum("relationship_intent", {"casual", "dating", "serious", "marriage_track"})
    has_kids = _enum("has_kids", {"yes", "no"})
    wants_kids = _enum("wants_kids", {"yes", "no", "maybe", "open"})
    relationship_structure = _enum("relationship_structure", {"monogamous", "enm", "poly", "open"})
    religion = data.get("religion") if isinstance(data.get("religion"), str) and data.get("religion").strip() else None
    religion_importance = _enum("religion_importance", {"not_important", "somewhat", "very"})
    drinks = _enum("drinks", {"never", "socially", "regularly"})
    smokes = _enum("smokes", {"never", "socially", "regularly"})
    cannabis = _enum("cannabis", {"never", "socially", "regularly"})

    traits = InferredTraits(
        attachment_style=attachment,
        love_language_giving=giving,
        love_language_receiving=receiving,
        conflict_style=conflict,
        relationship_history=history,
        name=extracted_name,
        gender=extracted_gender,
        current_city=current_city,
        gender_preference=gender_pref,
        cultural_preferences=cultural_prefs,
        birth_date=birth_date,
        birth_time_approx=birth_time_approx,
        birth_city=birth_city,
        dimension_weights=dimension_weights,
        emotional_giving=emotional_giving,
        emotional_needs=emotional_needs,
        interests=interests,
        personality=personality,
        partner_personality=partner_personality,
        values=values,
        partner_values=partner_values,
        lifestyle=lifestyle,
        age_min=age_min,
        age_max=age_max,
        max_distance_km=max_distance_km,
        relationship_intent=relationship_intent,
        has_kids=has_kids,
        wants_kids=wants_kids,
        relationship_structure=relationship_structure,
        religion=religion,
        religion_importance=religion_importance,
        drinks=drinks,
        smokes=smokes,
        cannabis=cannabis,
    )

    return traits, narrative, low_conf


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
        logger.error("Failed to parse coverage response: %s", response.content[0].text[:200])
        return {dim: 0.0 for dim in TRAIT_DIMENSIONS}

    coverage = {}
    for dim in TRAIT_DIMENSIONS:
        val = data.get(dim, 0.0)
        coverage[dim] = max(0.0, min(1.0, float(val)))

    return coverage
