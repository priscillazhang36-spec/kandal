"""Celebrity forced-choice pair generator for the visual-profile sub-stage.

After the Stage 0 dealbreaker MCQs finish, the engine fires ONE LLM call here
to generate 2-3 forced-choice celebrity pairs tailored to the user's
gender_preference + ethnicity_preference. Each pair contrasts two well-known
celebrities on a distinct visual/energy axis. The user's picks reveal their
real visual pull pattern (which the abstract `visual_type` MCQ couldn't).

The "what tipped it" reply is captured verbatim alongside the choice and
flows into the final artifact via the main extractor.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from kandal.core.config import get_settings

logger = logging.getLogger(__name__)


CELEBRITY_GENERATOR_SYSTEM_PROMPT = """\
You are designing a visual-preference forced-choice exercise. The user has \
just answered Stage 0 MCQs about who they're looking for (gender, age range, \
ethnicity preference, etc.). You will generate 2-3 contrasting celebrity \
pairs — each pair is two well-known real people the user must pick between \
to surface their actual visual / energy pull pattern.

INPUT FORMAT (provided by the user message):
- gender_preference: list like ["male"] or ["female"] or ["male","female","nonbinary"]
- ethnicity_preference: list like ["any"] or specific values (e.g. \
["white","asian"]). "any" means no constraint.
- age_min, age_max: rough age window the user is looking for

YOUR JOB:
1. Generate 2-3 forced-choice pairs. Each pair is two GLOBALLY WELL-KNOWN \
celebrities — actors, musicians, athletes, public figures the average user \
will recognize by name. Bias HEAVILY toward recognizability over obscure or \
indie choices. Both celebrities in a pair should be roughly in the user's \
age_min..age_max window (give or take 5 years).

2. Each pair must CONTRAST on a distinct visual/energy axis. Examples of axes:
   - classic-polished vs. soft-distinctive (e.g. Henry Cavill vs. Timothée Chalamet)
   - warm-grounded vs. brooding-intense (e.g. Pedro Pascal vs. Cillian Murphy)
   - boyish-approachable vs. mature-presence-heavy
   - sharp-corporate vs. casual-unstudied
   - athletic-built vs. lean-fine-featured
Pick 2-3 different axes — don't repeat the same dimension.

3. RESPECT THE FILTERS:
   - gender_preference: every celebrity must match the gender(s) listed. For \
multi-gender prefs, pick celebrities of the FIRST listed gender for \
consistency (don't mix genders within a pair).
   - ethnicity_preference: if "any", no constraint. If specific (e.g. \
["white","asian"]), every celebrity must match one of those ethnicities. If \
the user listed multiple ethnicities, you can have different pairs each \
represent a different listed ethnicity (e.g. one pair of white celebrities, \
one pair of Asian celebrities) — this gives the user real choice within \
their stated frame.
   - age range: celebrities should plausibly fit the user's stated age \
range. Don't pair a 22-year-old with a 60-year-old unless the user's range \
is "any".

4. For each celebrity, include a 5-12 word descriptor — the look/energy in \
their own grammar, NOT generic dating-app language. Examples:
   - "sharp jawline, classic-masculine build, polished demeanor"
   - "soft features, slim, distinctive style, intellectual"
   - "warm presence, grounded, salt-and-pepper, magnetic"
   - "boyish, approachable, expressive eyes"
The descriptor helps users who don't recognize the name still get the type.

5. RETURN STRICT JSON ONLY (no markdown, no commentary):
[
  {
    "axis": "short_lowercase_label",
    "a": {"name": "Celebrity Name", "descriptor": "5-12 word look + energy"},
    "b": {"name": "Celebrity Name", "descriptor": "5-12 word look + energy"}
  },
  ...
]

Generate 2 or 3 pairs. Quality over quantity — 2 sharp contrasts beats 3 \
muddy ones. Recognizability is the most important constraint.
"""


def _get_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _parse_json_response(raw: str) -> Any:
    if "```" in raw:
        raw = raw.split("```json")[-1].split("```")[0] if "```json" in raw else raw.split("```")[1].split("```")[0]
    return json.loads(raw.strip())


def generate_celebrity_pairs(
    gender_preference: list[str],
    ethnicity_preference: list[str],
    age_min: int | None,
    age_max: int | None,
) -> list[dict]:
    """One LLM call. Returns 2-3 forced-choice celebrity pairs.

    Shape: [{"axis": str, "a": {"name": str, "descriptor": str},
             "b": {"name": str, "descriptor": str}}, ...]

    Raises on LLM/JSON failure — caller decides how to handle (engine skips
    the celebrity stage on exception).
    """
    payload = {
        "gender_preference": gender_preference,
        "ethnicity_preference": ethnicity_preference or ["any"],
        "age_min": age_min,
        "age_max": age_max,
    }
    user_message = (
        "Generate 2-3 celebrity forced-choice pairs for this user.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )

    client = _get_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=CELEBRITY_GENERATOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text
    try:
        pairs = _parse_json_response(raw)
    except (json.JSONDecodeError, IndexError) as e:
        # Re-raised — caller logs at warning. Debug here keeps the raw output
        # available locally without paging Sentry.
        logger.debug("celebrity generator returned invalid JSON: %s | raw=%s", e, raw[:400])
        raise

    if not isinstance(pairs, list) or len(pairs) < 2:
        logger.debug("celebrity generator returned wrong shape: %s", pairs)
        raise ValueError("celebrity generator must return a list of >= 2 pairs")

    valid: list[dict] = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        axis = p.get("axis")
        a = p.get("a")
        b = p.get("b")
        if not (isinstance(axis, str) and isinstance(a, dict) and isinstance(b, dict)):
            continue
        if not (a.get("name") and a.get("descriptor") and b.get("name") and b.get("descriptor")):
            continue
        valid.append({
            "axis": axis,
            "a": {"name": str(a["name"]).strip(), "descriptor": str(a["descriptor"]).strip()},
            "b": {"name": str(b["name"]).strip(), "descriptor": str(b["descriptor"]).strip()},
        })

    if len(valid) < 2:
        logger.debug("celebrity generator produced < 2 valid pairs after filtering: %s", pairs)
        raise ValueError("celebrity generator must return >= 2 valid pairs")

    return valid[:3]


def format_celebrity_pair(pair: dict, pair_index: int, total: int) -> str:
    """Format a single celebrity pair into a user-facing prompt."""
    a = pair["a"]
    b = pair["b"]
    return (
        f"Look-pair {pair_index + 1} of {total}:\n\n"
        f"A) {a['name']} — {a['descriptor']}\n\n"
        f"B) {b['name']} — {b['descriptor']}\n\n"
        "Who pulls you more — and what tipped it? (Or say neither if neither lands.)"
    )


def parse_pick(user_reply: str) -> str:
    """Map a freeform user reply to 'a' | 'b' | 'neither'.

    A/B at word boundary wins. Then check for neither/either/both signals.
    Anything else → 'neither' (best-effort — we still capture the user's
    verbatim reply for the artifact).
    """
    import re
    cleaned = user_reply.strip().upper()
    m = re.search(r"(?<![A-Z])([AB])(?![A-Z])", cleaned)
    if m:
        return m.group(1).lower()
    lower = user_reply.strip().lower()
    if any(w in lower for w in ("neither", "either", "both", "no preference", "don't know", "idk", "none")):
        return "neither"
    return "neither"
