"""Stage 0 dealbreaker MCQs for ideal_type_discovery mode.

Fast partner-facing logistical filters answered up front so the conversational
core (past-pull excavation + vignettes) isn't wasted on incompatible imagining.
The Stage 3 vignette generator also reads these so vignettes respect hard
filters (gender, religion, smoking/drinking/cannabis, kids).

Deterministic MCQ loop — no LLM, no hallucination. Mirrors the shape of
`basics.py`: each question has a key, prompt, parse, and skip-if-known.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class DealbreakerQuestion:
    key: str                              # field on the ideal_type artifact
    prompt: str                           # what to send the user
    parse: Callable[[str], object | None] # None → re-ask
    skip_if_known: Callable[[dict], bool] # answers dict → already have it


def _letter(text: str, valid: set[str]) -> str | None:
    """Extract a standalone MCQ letter. Copy of basics._letter."""
    cleaned = text.strip().upper()
    for m in re.finditer(r"(?<![A-Z])([A-Z])(?![A-Z])", cleaned):
        ch = m.group(1)
        if ch in valid:
            return ch
    for ch in cleaned:
        if ch in valid:
            return ch
    return None


def _parse_gender_pref(text: str) -> list[str] | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {
        "A": ["male"],
        "B": ["female"],
        "C": ["nonbinary"],
        "D": ["male", "female", "nonbinary"],
    }
    if letter in mapping:
        return mapping[letter]
    t = text.lower()
    out: list[str] = []
    if "man" in t or "men" in t or "male" in t or "guy" in t:
        out.append("male")
    if "woman" in t or "women" in t or "female" in t:
        out.append("female")
    if "nonbinary" in t or "non-binary" in t or "enby" in t:
        out.append("nonbinary")
    return out or None


_AGE_LETTER_MAP = {
    "A": (20, 25),
    "B": (25, 30),
    "C": (30, 35),
    "D": (35, 40),
    "E": (40, 50),
    "F": (18, 80),
}


def _parse_age_range(text: str) -> tuple[int, int] | None:
    nums = [int(n) for n in re.findall(r"\d{1,2}", text) if 18 <= int(n) <= 80]
    if len(nums) >= 2:
        lo, hi = sorted(nums[:2])
        return (lo, hi)
    letter = _letter(text, set(_AGE_LETTER_MAP))
    if letter is None:
        return None
    return _AGE_LETTER_MAP[letter]


def _parse_ethnicity_pref(text: str) -> list[str] | None:
    letter = _letter(text, {"A", "B"})
    if letter == "A":
        return ["any"]
    if letter == "B":
        # Strip the "B" prefix and take the rest as freeform
        cleaned = re.sub(r"^\s*b[\s,:.-]*", "", text.strip(), flags=re.I)
        return [cleaned.lower()] if cleaned else None
    t = text.strip().lower()
    if t in {"any", "open", "no preference", "none", "all"}:
        return ["any"]
    return [t] if t else None


def _parse_religion_pref(text: str) -> list[str] | None:
    letter = _letter(text, {"A", "B", "C"})
    if letter == "A":
        return ["any"]
    if letter == "B":
        return ["same_as_mine"]
    if letter == "C":
        cleaned = re.sub(r"^\s*c[\s,:.-]*", "", text.strip(), flags=re.I)
        return [cleaned.lower()] if cleaned else None
    t = text.strip().lower()
    if t in {"any", "open", "no preference", "none"}:
        return ["any"]
    return [t] if t else None


def _parse_substance_tolerance(text: str) -> str | None:
    """Used for smoking / drinking / cannabis. A=none, B=sometimes/social, C=fine."""
    letter = _letter(text, {"A", "B", "C"})
    return {"A": "none", "B": "sometimes", "C": "yes"}.get(letter)


def _parse_drinks_tolerance(text: str) -> str | None:
    """Drinking has 3 tiers: none / social / heavy."""
    letter = _letter(text, {"A", "B", "C"})
    return {"A": "none", "B": "social", "C": "heavy"}.get(letter)


def _parse_partner_kids(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C"})
    return {"A": "yes", "B": "no", "C": "open"}.get(letter)


def _parse_intent(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C"})
    return {"A": "long_term", "B": "casual", "C": "open"}.get(letter)


def _parse_visual_importance(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    return {
        "A": "high",
        "B": "secondary",
        "C": "low",
        "D": "open",
    }.get(letter)


QUESTIONS: list[DealbreakerQuestion] = [
    DealbreakerQuestion(
        key="gender_preference",
        prompt=(
            "Who are you looking for?\n\n"
            "A) Men\n"
            "B) Women\n"
            "C) Non-binary folks\n"
            "D) Open to all"
        ),
        parse=_parse_gender_pref,
        skip_if_known=lambda a: bool(a.get("gender_preference")),
    ),
    DealbreakerQuestion(
        key="_age_range",  # writes to age_min + age_max
        prompt=(
            "What age range works?\n\n"
            "A) 20-25\n"
            "B) 25-30\n"
            "C) 30-35\n"
            "D) 35-40\n"
            "E) 40-50\n"
            "F) Open to any age\n\n"
            "Or tell me a specific range (e.g. 28-38)."
        ),
        parse=_parse_age_range,
        skip_if_known=lambda a: a.get("age_min") is not None and a.get("age_max") is not None,
    ),
    DealbreakerQuestion(
        key="ethnicity_preference",
        prompt=(
            "Any ethnicity preference?\n\n"
            "A) Open to all\n"
            "B) I have a preference (tell me)"
        ),
        parse=_parse_ethnicity_pref,
        skip_if_known=lambda a: bool(a.get("ethnicity_preference")),
    ),
    DealbreakerQuestion(
        key="religion_preference",
        prompt=(
            "Religion preference for a partner?\n\n"
            "A) Open to any\n"
            "B) Same as mine\n"
            "C) Specific (tell me)"
        ),
        parse=_parse_religion_pref,
        skip_if_known=lambda a: bool(a.get("religion_preference")),
    ),
    DealbreakerQuestion(
        key="relationship_intent",
        prompt=(
            "What are you looking for right now?\n\n"
            "A) Long-term / serious\n"
            "B) Casual / seeing what's there\n"
            "C) Open either way"
        ),
        parse=_parse_intent,
        skip_if_known=lambda a: bool(a.get("relationship_intent")),
    ),
    DealbreakerQuestion(
        key="partner_wants_kids",
        prompt=(
            "Kids — what do you want from a partner?\n\n"
            "A) They should want kids\n"
            "B) They should NOT want kids\n"
            "C) Open either way"
        ),
        parse=_parse_partner_kids,
        skip_if_known=lambda a: bool(a.get("partner_wants_kids")),
    ),
    DealbreakerQuestion(
        key="partner_smokes_max",
        prompt=(
            "Smoking — most you'd accept from a partner?\n\n"
            "A) Deal-breaker — none at all\n"
            "B) Sometimes is okay\n"
            "C) Fine either way"
        ),
        parse=_parse_substance_tolerance,
        skip_if_known=lambda a: bool(a.get("partner_smokes_max")),
    ),
    DealbreakerQuestion(
        key="partner_drinks_max",
        prompt=(
            "Drinking — most you'd accept?\n\n"
            "A) None / sober only\n"
            "B) Social drinking is fine\n"
            "C) Heavy drinking is fine"
        ),
        parse=_parse_drinks_tolerance,
        skip_if_known=lambda a: bool(a.get("partner_drinks_max")),
    ),
    DealbreakerQuestion(
        key="partner_cannabis_max",
        prompt=(
            "Cannabis — most you'd accept?\n\n"
            "A) Deal-breaker — none\n"
            "B) Sometimes is okay\n"
            "C) Fine either way"
        ),
        parse=_parse_substance_tolerance,
        skip_if_known=lambda a: bool(a.get("partner_cannabis_max")),
    ),
    DealbreakerQuestion(
        key="visual_importance",
        prompt=(
            "Last one — how much do looks actually matter to you?\n\n"
            "A) A lot — they need to be visually striking\n"
            "B) Matters, but secondary to how they make me feel\n"
            "C) Barely registers — minds and presence matter way more\n"
            "D) Open / depends on the person"
        ),
        parse=_parse_visual_importance,
        skip_if_known=lambda a: bool(a.get("visual_importance")),
    ),
]


def next_question(answers: dict, index: int) -> tuple[DealbreakerQuestion, int] | None:
    """Return the next unanswered question and its index, or None if done."""
    i = index
    while i < len(QUESTIONS):
        q = QUESTIONS[i]
        if q.skip_if_known(answers):
            i += 1
            continue
        return q, i
    return None


def apply_answer(answers: dict, question: DealbreakerQuestion, parsed) -> None:
    """Write parsed answer to the answers dict. Handles composite keys."""
    if question.key == "_age_range":
        lo, hi = parsed
        answers["age_min"] = lo
        answers["age_max"] = hi
    else:
        answers[question.key] = parsed
