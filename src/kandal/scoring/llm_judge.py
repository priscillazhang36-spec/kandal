"""LLM-based pairwise compatibility judge — Stage 3 of the matching pipeline.

Stages:
1. dealbreakers.passes_dealbreakers (hard filter)
2. engine.score_compatibility (coarse ranker — weighted dimensions + embeddings)
3. THIS MODULE (LLM judge on the top-K finalists per user)

The LLM sees both narratives + key traits and returns a structured verdict.
Embeddings can blur nuance; this stage catches what the coarse score misses.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

from kandal.core.config import get_settings
from kandal.models.preferences import Preferences
from kandal.models.profile import Profile

logger = logging.getLogger(__name__)


@dataclass
class LLMVerdict:
    score: float          # 0.0 – 1.0
    summary: str          # 1–2 sentence "why these two"
    reasons: list[str]    # up to 3 concrete compatibility points
    concerns: list[str]   # up to 2 honest concerns / friction points


_JUDGE_SYSTEM = """\
You are a sharp, honest matchmaker. You're looking at two people whose AI \
friends (Kandals) think they might be a fit. Your job is to give a real read \
on whether they'd actually click — not a polite read.

You will see each person's narrative profile and the key traits their Kandal \
extracted. You are not graded on optimism. Most pairs are not great fits and \
should score below 0.6. Reserve 0.8+ for pairs where you can clearly see them \
working. Reserve 0.9+ for rare standouts.

Think about:
- Whether their emotional needs and giving styles meet each other
- Whether their conflict styles will collide or repair
- Whether their attachment patterns are likely to spiral or stabilize
- Whether their values, interests, and lifestyle have enough overlap to share a life
- Whether either has stated preferences the other clearly doesn't meet

Be honest about concerns even when scoring high. If they're a strong fit but \
one person is recently out of an LTR, that's a concern worth noting.

Return ONLY valid JSON, no preamble:
{
  "score": <float 0.0-1.0>,
  "summary": "<one or two sentences explaining the read>",
  "reasons": ["<concrete reason 1>", "<reason 2>", "<reason 3>"],
  "concerns": ["<concern 1>", "<concern 2>"]
}

Keep reasons and concerns short — phrases, not paragraphs. Empty arrays are \
fine if there's nothing to say.
"""


def _format_person(label: str, profile: Profile, prefs: Preferences) -> str:
    parts = [f"=== Person {label} ==="]
    if profile.name:
        parts.append(f"Name: {profile.name}")
    if profile.age:
        parts.append(f"Age: {profile.age}")
    if profile.gender:
        parts.append(f"Gender: {profile.gender}")
    if getattr(profile, "city", None):
        parts.append(f"City: {profile.city}")
    if getattr(profile, "narrative", None):
        parts.append(f"\nNarrative:\n{profile.narrative}")
    if getattr(profile, "emotional_giving", None):
        parts.append(f"\nHow they love: {profile.emotional_giving}")
    if getattr(profile, "emotional_needs", None):
        parts.append(f"What they need: {profile.emotional_needs}")

    parts.append("\nTraits:")
    if prefs.attachment_style:
        parts.append(f"- attachment: {prefs.attachment_style}")
    if prefs.conflict_style:
        parts.append(f"- conflict: {prefs.conflict_style}")
    if prefs.relationship_history:
        parts.append(f"- history: {prefs.relationship_history}")
    if prefs.love_language_giving:
        parts.append(f"- gives love via: {', '.join(prefs.love_language_giving[:3])}")
    if prefs.love_language_receiving:
        parts.append(f"- receives love via: {', '.join(prefs.love_language_receiving[:3])}")
    if getattr(prefs, "interests", None):
        parts.append(f"- interests: {', '.join(prefs.interests)}")
    if getattr(prefs, "values", None):
        parts.append(f"- values: {', '.join(prefs.values)}")
    if getattr(prefs, "personality", None):
        parts.append(f"- personality: {', '.join(prefs.personality)}")
    if getattr(prefs, "partner_personality", None):
        parts.append(f"- wants partner who is: {', '.join(prefs.partner_personality)}")
    if getattr(prefs, "cultural_preferences", None):
        parts.append(f"- cultural preferences: {', '.join(prefs.cultural_preferences)}")

    return "\n".join(parts)


def judge_pair(
    profile_a: Profile,
    prefs_a: Preferences,
    profile_b: Profile,
    prefs_b: Preferences,
    coarse_score: float | None = None,
) -> LLMVerdict | None:
    """Run the LLM compatibility judge on a single pair. Returns None on failure."""
    payload = (
        f"{_format_person('A', profile_a, prefs_a)}\n\n"
        f"{_format_person('B', profile_b, prefs_b)}\n"
    )
    if coarse_score is not None:
        payload += (
            f"\n(For context only — coarse algorithmic score: {coarse_score:.2f}. "
            "Don't anchor on it; trust your own read.)\n"
        )

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": payload}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json").strip()
        data = json.loads(text)
        return LLMVerdict(
            score=max(0.0, min(1.0, float(data["score"]))),
            summary=str(data.get("summary", "")).strip(),
            reasons=[str(r).strip() for r in (data.get("reasons") or [])][:3],
            concerns=[str(c).strip() for c in (data.get("concerns") or [])][:2],
        )
    except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
        logger.warning("llm judge parse failed: %s", e)
        return None
    except Exception as e:
        logger.error("llm judge call failed: %s", e)
        return None
