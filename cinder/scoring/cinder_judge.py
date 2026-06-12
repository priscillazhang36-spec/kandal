"""Cinder LLM judge — the single scorer for cinder matching (Stage 2).

Unlike the main pipeline (which splits a deterministic dealbreaker filter from
the LLM judge), cinder uses the LLM for ALL aspects: it reads both people and
returns one spark-first score per woman-man pair. MBTI is weighted heavily and
cross-compared against what the other person is looking for; the stated top-3
preferences are given in priority order.

Mirrors src/kandal/scoring/llm_judge.py (LLMVerdict, model, parse/clamp shape).
"""

from __future__ import annotations

import json
import logging

import anthropic

from kandal.core.config import get_settings
from kandal.models.cinder import CinderProfile
from kandal.models.ideal_type import IdealType
from kandal.scoring.cinder_prefs import _humanize, _split_csv, parse_preferences, render_prefs
from kandal.scoring.llm_judge import DEFAULT_JUDGE_MODEL, LLMVerdict

logger = logging.getLogger(__name__)

_BIG_FIVE = [
    ("extroversion", "extroversion"),
    ("agreeableness", "agreeableness"),
    ("conscientiousness", "conscientiousness"),
    ("neuroticism", "neuroticism"),
    ("openness", "openness"),
]

_ACTIVITY = {1: "rarely active", 2: "somewhat active", 3: "regularly active", 4: "very active"}
_ALCOHOL = {1: "doesn't really drink", 2: "drinks socially", 3: "drinks regularly"}
_SMOKING = {1: "non-smoker", 2: "smokes socially", 3: "smokes", 4: "heavy smoker"}
_CANNABIS = {1: "no cannabis", 2: "cannabis socially", 3: "cannabis regularly"}


_CINDER_JUDGE_SYSTEM = """\
You're a matchmaker reading a woman's and a man's profile for a curated dating \
event. Don't checklist them. Imagine their actual first date — Tuesday, 8pm, \
somewhere in the city. Picture the table, the silences between turns, who orders \
first, what's said in the gap before the food arrives.

Walk through the first 20 minutes in your head and write it as a scene:
- What's the first concrete thing they bond over (or fail to), drawn from a real \
artifact in their profiles?
- When does one of them light up? Does the other notice and meet it?
- Where does it get awkward? Does it recover, or does the temperature drop?
- By 8:30, are they leaning in or politely playing the clock?

WEIGH MBTI HEAVILY. Each person's MBTI type is a strong read of their hidden \
temperament — how they recharge, decide, and handle conflict. Do two things with it:
1. Reason about how these two specific types actually interact on a date (e.g. an \
INTJ's clipped certainty against an ENFP's expansive riffing — friction or spark?).
2. Check each person's type against WHAT THE OTHER SAYS THEY WANT — the woman's \
"what she's drawn to" paragraph and BOTH people's ranked top-3 preferences. A type \
that embodies what the other is looking for is a strong positive; one that \
contradicts it is a real concern. Name the MBTI reasoning explicitly in reasons/concerns.

RESPECT PREFERENCE PRIORITY. The ranked preferences are in priority order — \
Priority 1 matters most, Priority 3 least. Weight how well this person satisfies \
the other's #1 priority far above their #3.

HER IDEAL TYPE — when the woman's card has a "HER IDEAL TYPE" block, weigh it ABOVE \
everything else; it's a deep read of her actual dating pattern. Three parts:
1. pull_pattern + the traits she's drawn to = her POSITIVE TARGET. Does THIS man, \
in how he'd actually show up on the date (not on paper), embody it? Reward a true hit hard.
2. BREAK PATTERN = the failure mode her relationships keep hitting. If this man \
plausibly re-creates it, that's a serious red flag — penalize heavily.
3. ICKS = instant, dealbreaker-grade turn-offs. If anything about this man reads as \
one of her icks — even a plausible on-the-date version of it — it should TANK the \
score and cap him out of her top matches, however strong he is elsewhere. Spark \
does not survive an ick.
For these women, go deeper: the scene and the reasons/concerns must explicitly name \
pull-fit, break-risk, and any ick flags you spot.

Everything else (qualities, hobbies, lifestyle, attractiveness, occupation) is RAW \
MATERIAL for the scene, not dimensions to tick off. Two people with overlapping \
hobbies can be a dead date if their temperaments don't talk to each other.

After writing the scene, score FROM the scene — what actually happened in the 20 \
minutes — not from a separate checklist.

Score distribution:
- Most pairs lack spark and should score below 0.6.
- 0.7+ for pairs where they'd both be telling a friend about the date later.
- 0.8+ for pairs where the conversation writes itself.
- 0.9+ for rare standouts where the spark is undeniable.

You are not graded on optimism.

Return ONLY valid JSON, no preamble:
{
  "scene": "<150-200 words, the imagined first 20 minutes — name specific artifacts \
from each profile and render at least one moment of click or miss>",
  "score": <float 0.0-1.0>,
  "summary": "<one sentence: what the scene tells us>",
  "reasons": ["<concrete moment that worked — cite MBTI/priority fit where relevant>", "<...>", "<...>"],
  "concerns": ["<concrete moment that didn't land or a real deal-killer>", "<...>"]
}

Reasons and concerns should cite specific moments from the scene, not generic trait \
labels. Empty arrays are fine.
"""


def _humanize_list(csv: str | None, limit: int = 12) -> str | None:
    toks = _split_csv(csv)
    if not toks:
        return None
    return ", ".join(_humanize(t) for t in toks[:limit])


def _lifestyle_line(p: CinderProfile) -> str | None:
    bits = []
    if p.activity_score in _ACTIVITY:
        bits.append(_ACTIVITY[p.activity_score])
    if p.alcohol_score in _ALCOHOL:
        bits.append(_ALCOHOL[p.alcohol_score])
    if p.smoking_score in _SMOKING:
        bits.append(_SMOKING[p.smoking_score])
    if p.cannabis_score in _CANNABIS:
        bits.append(_CANNABIS[p.cannabis_score])
    return ", ".join(bits) if bits else None


def _format_ideal_type(it: "IdealType") -> str:
    """Render the deep ideal-type profile block (women who completed discovery)."""
    lines = ["\nHER IDEAL TYPE (deep profile — weigh this ABOVE everything else):"]
    if it.pull_pattern:
        lines.append(f"- what genuinely pulls her in: {it.pull_pattern.strip()}")
    if it.pull_pattern_quote:
        lines.append(f'  in her words: "{it.pull_pattern_quote.strip()}"')
    if it.partner_traits:
        lines.append(f"- traits she's drawn to (ranked): {', '.join(_humanize(t) for t in it.partner_traits)}")
    if it.break_pattern:
        lines.append(f"- BREAK PATTERN (what keeps ending it — a man who re-creates this is a red flag): {it.break_pattern.strip()}")
    if it.icks:
        lines.append(f"- ICKS (instant, dealbreaker-grade turn-offs): {'; '.join(it.icks)}")
    # one past-relationship quote pair for texture, if available
    for pp in (it.past_pulls or []):
        bq, kq = (pp.brought_quote or "").strip(), (pp.broke_quote or "").strip()
        if bq or kq:
            if bq:
                lines.append(f'  past pull, her words: "{bq}"')
            if kq:
                lines.append(f'  past break, her words: "{kq}"')
            break
    return "\n".join(lines)


def _format_person_cinder(
    label: str,
    p: CinderProfile,
    *,
    is_woman: bool,
    ideal_type: "IdealType | None" = None,
) -> str:
    parts = [f"=== Person {label} ({'woman' if is_woman else 'man'}) ==="]
    if p.full_name:
        parts.append(f"Name: {p.full_name}")
    header = []
    if p.age:
        header.append(f"age {p.age}")
    if p.occupation:
        header.append(p.occupation)
    if p.education_level:
        header.append(_humanize(p.education_level))
    if p.height:
        header.append(f"{p.height}cm")
    if p.body_type:
        header.append(_humanize(p.body_type))
    if header:
        parts.append(" · ".join(header))

    # MBTI foregrounded — primary signal.
    if p.mbti:
        parts.append(f"\nMBTI: {p.mbti.strip().upper()}  (weigh this heavily)")

    spark = []
    q = _humanize_list(p.qualities)
    if q:
        spark.append(f"- qualities: {q}")
    h = _humanize_list(p.hobbies)
    if h:
        spark.append(f"- hobbies: {h}")
    if p.social_energy:
        spark.append(f"- social energy: {_humanize(p.social_energy)}")
    big_five = [f"{name} {getattr(p, attr):g}/5" for attr, name in _BIG_FIVE if getattr(p, attr) is not None]
    if big_five:
        spark.append(f"- Big Five: {', '.join(big_five)}")
    if spark:
        parts.append("\nWho they are:")
        parts.extend(spark)

    prefs = parse_preferences(p)
    if prefs:
        parts.append(f"\nWhat they want (ranked, Priority 1 = most important):\n  {render_prefs(prefs)}")
    if is_woman and ideal_type is not None:
        # Deep ideal-type profile supersedes the truncated preference_profile.
        parts.append(_format_ideal_type(ideal_type))
    elif is_woman and p.preference_profile:
        parts.append(f'\nWhat she\'s drawn to (her words):\n  "{p.preference_profile.strip()}"')

    bg = []
    ls = _lifestyle_line(p)
    if ls:
        bg.append(f"lifestyle: {ls}")
    for field in ("ethnicity", "politics", "religion", "income_range", "wants_kids", "has_kids"):
        val = getattr(p, field)
        if val:
            bg.append(f"{field.replace('_', ' ')}: {_humanize(val) if '_' in str(val) else val}")
    if bg:
        parts.append("\nBackground (collision check only — don't upgrade the score for these):")
        parts.append("  " + "; ".join(bg))

    return "\n".join(parts)


def judge_pair_cinder(
    woman: CinderProfile,
    man: CinderProfile,
    model: str = DEFAULT_JUDGE_MODEL,
    ideal_type: "IdealType | None" = None,
) -> LLMVerdict | None:
    """Run the cinder spark judge on one woman-man pair. None on failure.

    When `ideal_type` is provided (the woman completed ideal_type_discovery), her
    card carries a deep profile and the judge weighs pull/break/icks heavily.
    """
    payload = (
        f"{_format_person_cinder('A', woman, is_woman=True, ideal_type=ideal_type)}\n\n"
        f"{_format_person_cinder('B', man, is_woman=False)}\n"
    )
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1000,
            system=_CINDER_JUDGE_SYSTEM,
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
        logger.warning("cinder judge parse failed: %s", e)
        return None
    except Exception as e:
        logger.error("cinder judge call failed: %s", e)
        return None
