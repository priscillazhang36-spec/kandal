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
        role = "Matchmaker" if msg["role"] == "assistant" else "User"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


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

    raw = response.content[0].text
    # Extract JSON from response (handle markdown code blocks)
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]
    data = json.loads(raw.strip())

    # Validate and normalize
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
    # Ensure all 5 are present
    for lang in VALID_LOVE_LANGUAGES:
        if lang not in giving:
            giving.append(lang)

    receiving = data.get("love_language_receiving", VALID_LOVE_LANGUAGES[:])
    receiving = [l for l in receiving if l in VALID_LOVE_LANGUAGES]
    for lang in VALID_LOVE_LANGUAGES:
        if lang not in receiving:
            receiving.append(lang)

    narrative = data.get("narrative", "")

    traits = InferredTraits(
        attachment_style=attachment,
        love_language_giving=giving,
        love_language_receiving=receiving,
        conflict_style=conflict,
        relationship_history=history,
    )

    return traits, narrative


def assess_coverage(messages: list[dict]) -> dict[str, float]:
    """Estimate trait coverage confidence from conversation so far.

    Uses claude-haiku-4-5 for speed (called every turn).
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

    raw = response.content[0].text
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]

    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to parse coverage response: %s", raw[:200])
        return {dim: 0.0 for dim in TRAIT_DIMENSIONS}

    coverage = {}
    for dim in TRAIT_DIMENSIONS:
        val = data.get(dim, 0.0)
        coverage[dim] = max(0.0, min(1.0, float(val)))

    return coverage
