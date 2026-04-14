"""Post-summary basics collection. Runs as a deterministic MCQ loop —
no LLM inference, so no hallucination is possible. Each question has a fixed
prompt, a fixed parser, and a skip condition if we already extracted it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from kandal.profiling.extractor import _normalize_birth_date, _normalize_birth_time


@dataclass
class BasicQuestion:
    key: str                              # field on InferredTraits to update
    prompt: str                           # what to send the user
    parse: Callable[[str], object | None] # None → re-ask
    skip_if_known: Callable[[dict], bool] # traits dict → already have it


def _letter(text: str, valid: set[str]) -> str | None:
    """Extract an MCQ letter answer. Prefer a standalone letter (word-boundary
    match) so phrases like 'I picked A' resolve to 'A', not whatever letter
    appears first inside a word.
    """
    cleaned = text.strip().upper()
    # Standalone letter: surrounded by whitespace/punctuation/start/end.
    for m in re.finditer(r"(?<![A-Z])([A-Z])(?![A-Z])", cleaned):
        ch = m.group(1)
        if ch in valid:
            return ch
    # Fallback: any letter in the valid set (handles "A." "A)" edge cases already
    # covered above, but also bare mid-word letters as last resort).
    for ch in cleaned:
        if ch in valid:
            return ch
    return None


def _parse_gender_pref(text: str) -> list[str] | None:
    letter = _letter(text, {"A", "B", "C", "D", "E"})
    mapping = {"A": ["male"], "B": ["female"], "C": ["nonbinary"], "D": ["male", "female", "nonbinary"]}
    if letter in mapping:
        return mapping[letter]
    if letter == "E":
        # Free-text: crude keyword pass
        t = text.lower()
        out: list[str] = []
        if "man" in t or "men" in t or "male" in t or "guy" in t:
            out.append("male")
        if "woman" in t or "women" in t or "female" in t:
            out.append("female")
        if "nonbinary" in t or "non-binary" in t or "enby" in t:
            out.append("nonbinary")
        return out or None
    return None


def _parse_cultural(text: str) -> list[str] | None:
    letter = _letter(text, {"A", "B"})
    if letter == "A":
        return []  # "no preference" — explicitly empty list
    if letter == "B":
        # Pull whatever they wrote; let the free-text speak for itself.
        cleaned = re.sub(r"^\s*b[\s,:.-]*", "", text.strip(), flags=re.I)
        return [cleaned] if cleaned else None
    # Accept plain free-text too ("asian", "open", etc.)
    stripped = text.strip()
    if stripped.lower() in {"none", "no", "no preference", "open", "any"}:
        return []
    return [stripped] if stripped else None


def _user_age(traits: dict) -> int | None:
    bd = traits.get("birth_date")
    if not bd:
        return None
    try:
        from datetime import date as _date
        d = _date.fromisoformat(bd)
        today = _date.today()
        age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
        return age if 18 <= age <= 99 else None
    except (ValueError, TypeError):
        return None


_AGE_LETTER_MAP = {
    "A": (20, 25),
    "B": (25, 30),
    "C": (30, 35),
    "D": (35, 40),
    "E": (40, 50),
    "F": (18, 80),  # open
}


def _parse_age_range(text: str, traits: dict | None = None) -> tuple[int, int] | None:
    """Accept '28-38', '28 to 38', or MCQ letters A-F (absolute 5-year buckets)."""
    nums = [int(n) for n in re.findall(r"\d{1,2}", text) if 18 <= int(n) <= 80]
    if len(nums) >= 2:
        lo, hi = sorted(nums[:2])
        return (lo, hi)

    letter = _letter(text, set(_AGE_LETTER_MAP))
    if letter is None:
        return None
    return _AGE_LETTER_MAP[letter]


def _parse_distance(text: str) -> int | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {"A": 25, "B": 50, "C": 200, "D": 99999}
    if letter in mapping:
        return mapping[letter]
    nums = re.findall(r"\d+", text)
    if nums:
        return int(nums[0])
    return None


def _parse_intent(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {"A": "casual", "B": "dating", "C": "serious", "D": "marriage_track"}
    return mapping.get(letter)


def _parse_yes_no(text: str) -> str | None:
    letter = _letter(text, {"A", "B"})
    mapping = {"A": "yes", "B": "no"}
    if letter in mapping:
        return mapping[letter]
    t = text.strip().lower()
    if t in {"yes", "y", "yeah", "yep"}:
        return "yes"
    if t in {"no", "n", "nope"}:
        return "no"
    return None


def _parse_wants_kids(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {"A": "yes", "B": "no", "C": "maybe", "D": "open"}
    return mapping.get(letter)


def _parse_structure(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {"A": "monogamous", "B": "enm", "C": "poly", "D": "open"}
    return mapping.get(letter)


def _parse_religion(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C"})
    mapping = {"A": "not_important", "B": "somewhat", "C": "very"}
    return mapping.get(letter)


def _parse_substances(text: str) -> dict | None:
    """Accept free-form like 'drinks socially, never smokes, weed sometimes'.

    Split by commas/semicolons/'and', then classify each fragment as applying
    to drinks/smokes/cannabis by substance keyword, level by label keyword.
    """
    t = text.lower().strip()
    if not t:
        return None
    fragments = re.split(r"[,;]|\band\b", t)
    substance_map = {
        "drinks": re.compile(r"drink|alcohol"),
        "smokes": re.compile(r"smok|tobacco|cigarette|vape"),
        "cannabis": re.compile(r"weed|cannabis|marijuana|thc|ganja"),
    }
    result: dict = {}
    for frag in fragments:
        frag = frag.strip()
        if not frag:
            continue
        # Which substance?
        target = None
        for key, pat in substance_map.items():
            if pat.search(frag):
                target = key
                break
        if target is None:
            continue
        # What level?
        if re.search(r"\bnever\b|don'?t|not at all|\bno\b", frag):
            level = "never"
        elif re.search(r"regular|daily|often|a lot", frag):
            level = "regularly"
        elif re.search(r"social|sometimes|occasional", frag):
            level = "socially"
        else:
            continue
        result[target] = level
    return result or None


def _parse_free_text(text: str) -> str | None:
    t = text.strip()
    return t or None


def _build_age_prompt(traits: dict) -> str:
    """Use the user's own birth year to suggest a reasonable range if we have it."""
    return (
        "What age range works for a partner?\n\n"
        "A) 5 years younger to 5 years older\n"
        "B) A bit younger to much older\n"
        "C) Open — I care more about the person than the number\n"
        "D) Tell me a specific range (e.g. 28-38)"
    )


QUESTIONS: list[BasicQuestion] = [
    BasicQuestion(
        key="gender_preference",
        prompt=(
            "Alright, just a few quick logistics and we're done.\n\n"
            "Who are you looking to date?\n\n"
            "A) Men\nB) Women\nC) Non-binary folks\nD) Open to all\n"
            "E) Tell me in your own words"
        ),
        parse=_parse_gender_pref,
        skip_if_known=lambda t: bool(t.get("gender_preference")),
    ),
    BasicQuestion(
        key="birth_date",
        prompt="What's your birthday? (Month/Day/Year — e.g. 11/28/1996)",
        parse=lambda s: _normalize_birth_date(s),
        skip_if_known=lambda t: bool(t.get("birth_date")),
    ),
    BasicQuestion(
        key="birth_time_approx",
        prompt=(
            "Any idea what time of day you were born? (Rough is fine — morning, "
            "afternoon, etc. Reply 'skip' if you don't know.)"
        ),
        parse=lambda s: None if s.strip().lower() in {"skip", "idk", "no", "unknown"} else _normalize_birth_time(s),
        skip_if_known=lambda t: bool(t.get("birth_time_approx")),
    ),
    BasicQuestion(
        key="birth_city",
        prompt="Where were you born? (city is fine)",
        parse=_parse_free_text,
        skip_if_known=lambda t: bool(t.get("birth_city")),
    ),
    BasicQuestion(
        key="current_city",
        prompt="And where are you based now?",
        parse=_parse_free_text,
        skip_if_known=lambda t: bool(t.get("current_city")),
    ),
    BasicQuestion(
        key="_age_range",  # special — writes to age_min + age_max
        prompt=(
            "What age range works for a partner?\n\n"
            "A) 20-25\n"
            "B) 25-30\n"
            "C) 30-35\n"
            "D) 35-40\n"
            "E) 40-50\n"
            "F) Open to any age\n"
            "Or tell me a specific range (e.g. 28-38)"
        ),
        parse=_parse_age_range,
        skip_if_known=lambda t: t.get("age_min") is not None and t.get("age_max") is not None,
    ),
    BasicQuestion(
        key="max_distance_km",
        prompt=(
            "How far are you willing to date?\n\n"
            "A) Same city only (~25km)\n"
            "B) Within ~50km\n"
            "C) Same region/state (~200km)\n"
            "D) Open to long distance"
        ),
        parse=_parse_distance,
        skip_if_known=lambda t: t.get("max_distance_km") is not None,
    ),
    BasicQuestion(
        key="relationship_intent",
        prompt=(
            "What are you actually looking for right now?\n\n"
            "A) Casual / seeing what's out there\n"
            "B) Dating, no rush\n"
            "C) Something serious\n"
            "D) Marriage-track"
        ),
        parse=_parse_intent,
        skip_if_known=lambda t: bool(t.get("relationship_intent")),
    ),
    BasicQuestion(
        key="has_kids",
        prompt="Do you have kids?\n\nA) Yes\nB) No",
        parse=_parse_yes_no,
        skip_if_known=lambda t: bool(t.get("has_kids")),
    ),
    BasicQuestion(
        key="wants_kids",
        prompt=(
            "Want kids someday?\n\n"
            "A) Yes\nB) No\nC) Maybe\nD) Open either way"
        ),
        parse=_parse_wants_kids,
        skip_if_known=lambda t: bool(t.get("wants_kids")),
    ),
    BasicQuestion(
        key="relationship_structure",
        prompt=(
            "Relationship structure you're into?\n\n"
            "A) Monogamous\nB) Ethically non-monogamous\nC) Polyamorous\n"
            "D) Open / figuring it out"
        ),
        parse=_parse_structure,
        skip_if_known=lambda t: bool(t.get("relationship_structure")),
    ),
    BasicQuestion(
        key="religion_importance",
        prompt=(
            "How important is religion or spirituality in a partner?\n\n"
            "A) Not important\nB) Somewhat\nC) Very important"
        ),
        parse=_parse_religion,
        skip_if_known=lambda t: bool(t.get("religion_importance")),
    ),
    BasicQuestion(
        key="_substances",  # writes to drinks/smokes/cannabis
        prompt=(
            "Quick lifestyle check — for each, are you never / socially / regularly?\n\n"
            "Drinking, smoking, weed. (Just reply in one line — e.g. 'drinks socially, "
            "never smoke, weed sometimes'.)"
        ),
        parse=_parse_substances,
        skip_if_known=lambda t: any(t.get(k) for k in ("drinks", "smokes", "cannabis")),
    ),
]


def next_question(traits: dict, index: int) -> tuple[BasicQuestion, int] | None:
    """Return the next unanswered BasicQuestion and its new index, or None if done."""
    i = index
    while i < len(QUESTIONS):
        q = QUESTIONS[i]
        if q.skip_if_known(traits):
            i += 1
            continue
        return q, i
    return None


def apply_answer(traits: dict, question: BasicQuestion, parsed) -> None:
    """Write parsed answer to the traits dict. Handles special composite keys."""
    if question.key == "_age_range":
        lo, hi = parsed
        traits["age_min"] = lo
        traits["age_max"] = hi
    elif question.key == "_substances":
        for k in ("drinks", "smokes", "cannabis"):
            if parsed.get(k):
                traits[k] = parsed[k]
    else:
        traits[question.key] = parsed
