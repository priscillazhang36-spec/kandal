"""LLM-based pairwise compatibility judge — Stage 2 of the matching pipeline.

Stages:
1. dealbreakers.passes_dealbreakers (hard filter)
2. THIS MODULE (LLM judge on every passing pair)

The LLM sees both narratives + key traits and returns a structured verdict.
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
    scene: str            # imagined first 20 minutes of the date
    summary: str          # 1 sentence: what the scene tells us
    reasons: list[str]    # up to 3 concrete moments from the scene
    concerns: list[str]   # up to 2 concrete moments that didn't land


_JUDGE_SYSTEM = """\
You're a matchmaker reading two profiles. Don't checklist them. Imagine their \
actual first date — Tuesday, 8pm, somewhere in the city. Picture the table, \
the silences between turns, who orders first, what's said in the gap before \
the food arrives.

Walk through the first 20 minutes in your head and write it as a scene. \
Specifically:
- What's the first concrete thing they bond over (or fail to bond over)? \
Drawn from a real artifact in their profiles, not abstract qualities.
- When does one of them light up? Does the other notice and meet it, or let \
it pass?
- Where does it get awkward? Does it recover, or does the temperature drop?
- By 8:30, are they leaning in or politely playing the clock?

The spark fields and long-term traits in the payload are RAW MATERIAL FOR \
YOUR IMAGINATION, not dimensions to match. Two grounded people with the same \
kid timeline can be a dead date if their taste worlds don't actually talk to \
each other. Two register-mismatched people (one aesthete, one utilitarian) \
rarely click on date one, even when their abstract values align. Trust your \
read of the cultural-tribe signal in their actual artifacts.

The narrative and emotional_giving / emotional_needs sections at the bottom \
are background. You may use them to spot a hard incompatibility that would \
tank the date (one needs constant reassurance, the other refuses emotional \
labor; one is in active grief, the other is honeymoon-energy). You may NOT \
use them to upgrade a score because the prose sounds emotionally compatible. \
Warm narrative is not spark.

After writing the scene, score from the scene. The score should follow from \
what actually happened in the 20 minutes you imagined — not from a separate \
trait checklist.

Score distribution:
- Most pairs lack spark and should score below 0.6.
- 0.7+ for pairs where they'd both be telling a friend about the date later.
- 0.8+ for pairs where the conversation writes itself.
- 0.9+ for rare standouts where the spark is undeniable.

You are not graded on optimism.

Return ONLY valid JSON, no preamble:
{
  "scene": "<150-200 words, the imagined first 20 minutes — name specific \
artifacts/places/topics from each profile, render at least one moment of \
either click or miss>",
  "score": <float 0.0-1.0>,
  "summary": "<one sentence: what the scene tells us>",
  "reasons": ["<concrete moment from the scene that worked>", "<...>", "<...>"],
  "concerns": ["<concrete moment that didn't land or a real deal-killer>", "<...>"]
}

Reasons and concerns should cite specific moments from the scene you just \
wrote, not generic restatements of trait labels. Empty arrays are fine.
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

    # v4: surface verbatim user-voice slices alongside paraphrased fields.
    # The quote is in the user's actual register/casing — it's the signal
    # paraphrase strips out (aesthete vs grounded, lyrical vs clipped).
    voice = getattr(profile, "spark_voice", None) or {}

    def _voice_line(quote_key: str) -> str | None:
        q = voice.get(quote_key) if isinstance(voice, dict) else None
        if not q or not isinstance(q, str):
            return None
        return f'  voice: "{q.strip()}"'

    spark_lines = []
    if getattr(profile, "current_obsession", None):
        spark_lines.append(f"- current obsession: {profile.current_obsession}")
        vl = _voice_line("current_obsession_quote")
        if vl:
            spark_lines.append(vl)
    if getattr(profile, "two_hour_topic", None):
        spark_lines.append(f"- could talk for two hours about: {profile.two_hour_topic}")
        vl = _voice_line("forever_topic_quote")
        if vl:
            spark_lines.append(vl)
    if getattr(profile, "taste_fingerprint", None):
        spark_lines.append(f"- taste fingerprint: {profile.taste_fingerprint}")
        vl = _voice_line("taste_fingerprint_quote")
        if vl:
            spark_lines.append(vl)
    if getattr(profile, "contradiction_hook", None):
        spark_lines.append(f"- contradiction: {profile.contradiction_hook}")
    if getattr(profile, "past_attraction", None):
        spark_lines.append(f"- past attraction pattern: {profile.past_attraction}")
        vl = _voice_line("pull_quote")
        if vl:
            spark_lines.append(vl)
    if getattr(profile, "favorite_places", None):
        place_names = [
            str(p.get("name") or p.get("place") or p)
            for p in profile.favorite_places
            if p
        ]
        if place_names:
            spark_lines.append(f"- favorite places: {', '.join(place_names)}")
    # Verbatim humor + giving moments (no paraphrased equivalent — the quote
    # IS the signal, not a label)
    humor_q = voice.get("humor_example_quote") if isinstance(voice, dict) else None
    if humor_q:
        spark_lines.append(f'- last hard laugh (verbatim): "{humor_q.strip()}"')
    giving_q = voice.get("giving_quote") if isinstance(voice, dict) else None
    if giving_q:
        spark_lines.append(f'- recent giving moment (verbatim): "{giving_q.strip()}"')
    if getattr(prefs, "energy_pace", None):
        spark_lines.append(f"- energy/pace: {prefs.energy_pace}")
    if getattr(prefs, "ambition_shape", None):
        spark_lines.append(f"- ambition shape: {prefs.ambition_shape}")
    # v4.1: appearance preference (what they're visually pulled toward)
    if getattr(prefs, "visual_type", None):
        spark_lines.append(f"- visual type they're pulled to: {prefs.visual_type}")
    if getattr(prefs, "visual_preference", None):
        spark_lines.append(f"- visual preference: {prefs.visual_preference}")
        vl = _voice_line("visual_pull_quote")
        if vl:
            spark_lines.append(vl)
    parts.append("\nSPARK SIGNALS (primary scoring inputs):")
    if spark_lines:
        parts.extend(spark_lines)
    else:
        parts.append("- (none extracted — score must be low)")

    parts.append("\nLong-term traits (collision check only):")
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

    bg_lines = []
    if getattr(profile, "narrative", None):
        bg_lines.append(f"Narrative:\n{profile.narrative}")
    if getattr(profile, "emotional_giving", None):
        bg_lines.append(f"How they love: {profile.emotional_giving}")
    if getattr(profile, "emotional_needs", None):
        bg_lines.append(f"What they need: {profile.emotional_needs}")
    if bg_lines:
        parts.append("\nBackground (raw material — only treat as a score input if it reveals an active deal-killer):")
        parts.extend(bg_lines)

    return "\n".join(parts)


DEFAULT_JUDGE_MODEL = "claude-haiku-4-5-20251001"


def judge_pair(
    profile_a: Profile,
    prefs_a: Preferences,
    profile_b: Profile,
    prefs_b: Preferences,
    model: str = DEFAULT_JUDGE_MODEL,
) -> LLMVerdict | None:
    """Run the LLM compatibility judge on a single pair. Returns None on failure."""
    payload = (
        f"{_format_person('A', profile_a, prefs_a)}\n\n"
        f"{_format_person('B', profile_b, prefs_b)}\n"
    )

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1000,
            system=_JUDGE_SYSTEM,
            messages=[{"role": "user", "content": payload}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json").strip()
        data = json.loads(text)
        return LLMVerdict(
            score=max(0.0, min(1.0, float(data["score"]))),
            scene=str(data.get("scene", "")).strip(),
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
