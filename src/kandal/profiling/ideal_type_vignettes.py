"""Stage 3 vignette generator for ideal_type_discovery.

After Stages 1+2 finish (past-pull excavation + ick), this module fires ONE
LLM call to generate 2-3 contrasting character vignette pairs tuned to the
user's past pulls and respecting their Stage 0 dealbreakers. The user then
picks one from each pair in Stage 3.

The "what tipped it" answer the user gives in response to each pair is more
valuable than the choice itself — it's where the verbatim signal lands.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from kandal.core.config import get_settings

logger = logging.getLogger(__name__)


VIGNETTE_GENERATOR_SYSTEM_PROMPT = """\
You are designing a forced-choice clarity exercise. The user has just narrated \
the arc of 1-2 past relationships (both what initially drew them in AND what \
broke things apart) and shared what gives them the "ick." You will generate \
2-3 contrasting character vignette pairs — pairs of plausible-real people \
where the user must pick which one pulls them more. The choice reveals their \
real preference pattern.

INPUT FORMAT (provided by the user message):
- past_pulls: list of past relationship arcs, each with description, \
what_brought_together (initial pull), what_broke_apart (the friction/end), \
and verbatim quotes for both
- icks: list of dealbreaker phrases
- dealbreakers: dict of partner-facing logistical filters (gender_preference, \
age range, religion_preference, smoking/drinking/cannabis tolerance, kids stance, \
relationship_intent, ethnicity_preference)

YOUR JOB:
1. Identify the 2-3 most salient IMPLIED axes — use BOTH the pull side and \
the break side of the arcs. The break pattern often points at the dimension \
the user is most ambivalent about (they were pulled but it didn't work — \
why?). Examples of axes: creative-output vs. service-orientation, \
high-presence vs. quiet-density, intellectual-edge vs. emotional-warmth, \
in-motion vs. settled, polished vs. unstudied, emotionally-expressive vs. \
emotionally-contained. If the break side revealed a specific friction (e.g. \
emotional withdrawal, mismatched ambition), at least one pair should contrast \
ON that dimension so the user can pick what they'd actually live with.

2. For each axis, generate ONE pair: two people who would BOTH plausibly be \
in the user's orbit (both could realistically pull them) but who differ \
primarily on that axis. Each vignette:
   - 30-50 words
   - Has named specifics: neighborhood/city, what they do, a small behavior \
tell (how they hold a coffee, what they posted last, the way a room shifts \
when they enter)
   - Avoids generic dating-app phrases ("loves adventure," "into fitness," \
"good vibes only")
   - Is a WHOLE PLAUSIBLE PERSON, not a foil

3. RESPECT THE DEALBREAKERS — both vignettes in every pair must satisfy:
   - gender_preference (only generate matching gender)
   - age range (age_min to age_max)
   - religion_preference (if not "any" or "same_as_mine")
   - smoking/drinking/cannabis tolerance (don't generate a heavy drinker if \
partner_drinks_max is "none")
   - partner_wants_kids (if "yes" → don't generate childfree person; if "no" \
→ don't generate someone who wants kids)
   - relationship_intent
A vignette that violates a hard filter breaks the exercise.

3a. USE THE VISUAL SIGNAL (when present in dealbreakers):
   - visual_type indicates the look that pulls them: classic / artsy / \
athletic / no_strong_type. If visual_importance is "high", lean BOTH vignettes \
in each pair toward visual_type so the visual baseline is met and contrast is \
about behavior / register, not body type. If visual_importance is "secondary" \
or "low" or unset, keep visual descriptions minimal and stay neutral on \
appearance — the user isn't here for that.
   - Use light, specific visual tells when relevant ("worn-in linen shirt," \
"runs on Sunday mornings," "stack of silver rings"). Never use generic dating-\
app body talk ("fit," "gorgeous," "stunning").

4. DO NOT echo the user's past-pull descriptions back at them. The vignettes \
should feel like new people, not their exes in disguise.

5. The choice should feel HARD. If one vignette is obviously better-aligned \
with their stated past pulls, you've failed — the point is to surface the \
preference they DON'T yet know.

RETURN STRICT JSON ONLY (no markdown, no commentary):
[
  {
    "axis": "short_lowercase_label",
    "a": {"name": "first name", "sketch": "30-50 word vignette"},
    "b": {"name": "first name", "sketch": "30-50 word vignette"}
  },
  ...
]

Generate 2 or 3 pairs. Quality over quantity — 2 sharp pairs beats 3 muddy ones.
"""


def _get_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _parse_json_response(raw: str) -> Any:
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())


def generate_vignettes(
    past_pulls: list[dict],
    icks: list[str],
    dealbreakers: dict,
) -> list[dict]:
    """Generate 2-3 forced-choice vignette pairs.

    Returns a list of dicts shaped like:
        [{"axis": str, "a": {"name": str, "sketch": str},
          "b": {"name": str, "sketch": str}}, ...]

    Raises on LLM failure — caller decides how to handle (engine retries once,
    then falls back to a single hand-rolled pair).
    """
    payload = {
        "past_pulls": past_pulls,
        "icks": icks,
        "dealbreakers": dealbreakers,
    }
    user_message = (
        "Generate 2-3 forced-choice vignette pairs for this user.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )

    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=VIGNETTE_GENERATOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text
    try:
        pairs = _parse_json_response(raw)
    except (json.JSONDecodeError, IndexError) as e:
        # Re-raised — caller logs at warning. Debug here for local visibility
        # without paging Sentry on every transient failure.
        logger.debug("vignette generator returned invalid JSON: %s | raw=%s", e, raw[:500])
        raise

    if not isinstance(pairs, list) or len(pairs) < 2:
        logger.debug("vignette generator returned wrong shape: %s", pairs)
        raise ValueError("vignette generator must return a list of >= 2 pairs")

    # Validate shape — each pair must have axis, a.name+sketch, b.name+sketch
    valid: list[dict] = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        axis = p.get("axis")
        a = p.get("a")
        b = p.get("b")
        if not (isinstance(axis, str) and isinstance(a, dict) and isinstance(b, dict)):
            continue
        if not (a.get("name") and a.get("sketch") and b.get("name") and b.get("sketch")):
            continue
        valid.append({
            "axis": axis,
            "a": {"name": str(a["name"]).strip(), "sketch": str(a["sketch"]).strip()},
            "b": {"name": str(b["name"]).strip(), "sketch": str(b["sketch"]).strip()},
        })

    if len(valid) < 2:
        logger.debug("vignette generator produced < 2 valid pairs after filtering: %s", pairs)
        raise ValueError("vignette generator must return >= 2 valid pairs")

    return valid[:3]  # cap at 3


def format_pair_for_user(pair: dict, pair_index: int, total: int) -> str:
    """Format a single vignette pair into the message Kandal sends the user."""
    a = pair["a"]
    b = pair["b"]
    return (
        f"Pair {pair_index + 1} of {total}:\n\n"
        f"A) {a['name']} — {a['sketch']}\n\n"
        f"B) {b['name']} — {b['sketch']}\n\n"
        "Who pulls you more — and what tipped it?"
    )
