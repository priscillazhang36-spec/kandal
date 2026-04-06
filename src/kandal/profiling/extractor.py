"""Extract structured traits from a profiling conversation using Claude."""

from __future__ import annotations

import json
import logging

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

    birth_date = data.get("birth_date")  # pass through as string
    birth_time_approx = data.get("birth_time_approx")
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
