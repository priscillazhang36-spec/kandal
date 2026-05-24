"""Spark scenario MCQs — the signals that predict whether two people click
on a first date. Runs as a deterministic loop after the freeform conversation,
before the logistics basics loop.

V4: trimmed from 4 dimensions to 2 — humor and conversational texture are now
collected via the freeform `recent_laugh` moment + voice slices across all
moments (richer than A/B/C/D for those signals). The remaining two MCQs cover
categorical lifestyle dispositions that don't narrate cleanly:
- energy/pace (how entangled/parallel)
- ambition shape (5-year posture)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class SparkQuestion:
    key: str                              # field on InferredTraits / preferences
    prompt: str                           # what to send the user
    parse: Callable[[str], object | None] # None → re-ask
    skip_if_known: Callable[[dict], bool] # traits dict → already have it


def _letter(text: str, valid: set[str]) -> str | None:
    """Extract a standalone MCQ letter (word-boundary). Copy of basics._letter."""
    cleaned = text.strip().upper()
    for m in re.finditer(r"(?<![A-Z])([A-Z])(?![A-Z])", cleaned):
        ch = m.group(1)
        if ch in valid:
            return ch
    for ch in cleaned:
        if ch in valid:
            return ch
    return None


def _parse_energy(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {
        "A": "entangled",
        "B": "balanced",
        "C": "independent",
        "D": "parallel",
    }
    return mapping.get(letter)


def _parse_ambition(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {
        "A": "builder",
        "B": "master",
        "C": "free",
        "D": "rooted",
    }
    return mapping.get(letter)


def _parse_visual_type(text: str) -> str | None:
    letter = _letter(text, {"A", "B", "C", "D"})
    mapping = {
        "A": "classic",          # put-together, polished
        "B": "artsy",            # specific, expressive
        "C": "athletic",         # outdoorsy, active build
        "D": "no_strong_type",   # face/energy over body type
    }
    return mapping.get(letter)


QUESTIONS: list[SparkQuestion] = [
    SparkQuestion(
        key="energy_pace",
        prompt=(
            "Your ideal relationship rhythm:\n\n"
            "A) Best friends who see each other most days and never get tired of it\n"
            "B) Intense together-time and real separate lives — both matter\n"
            "C) We're our own full people who happen to meet in the middle\n"
            "D) Entangled but quiet — parallel lives, often in the same room"
        ),
        parse=_parse_energy,
        skip_if_known=lambda t: bool(t.get("energy_pace")),
    ),
    SparkQuestion(
        key="ambition_shape",
        prompt=(
            "Five years from now, things went well. Your life looks like:\n\n"
            "A) I built something — a company, a project, work people know about\n"
            "B) I'm really good at what I do. Stable, respected, growing\n"
            "C) Maximum freedom — I work on my terms, travel when I want\n"
            "D) Rooted. A home, a community, a routine that feels like mine"
        ),
        parse=_parse_ambition,
        skip_if_known=lambda t: bool(t.get("ambition_shape")),
    ),
    SparkQuestion(
        key="visual_type",
        prompt=(
            "Last one — which best matches the look that pulls you in?\n\n"
            "A) Classic / put-together — well-dressed, polished, takes care of themselves\n"
            "B) Artsy / specific — has a distinctive style, expressive, a little weird\n"
            "C) Athletic / outdoorsy — active build, comfortable in their body, sun on them\n"
            "D) No strong type — it's mostly about the face or the energy, not the body"
        ),
        parse=_parse_visual_type,
        skip_if_known=lambda t: bool(t.get("visual_type")),
    ),
]


def next_question(traits: dict, index: int) -> tuple[SparkQuestion, int] | None:
    """Return the next unanswered SparkQuestion and its new index, or None if done."""
    i = index
    while i < len(QUESTIONS):
        q = QUESTIONS[i]
        if q.skip_if_known(traits):
            i += 1
            continue
        return q, i
    return None


def apply_answer(traits: dict, question: SparkQuestion, parsed) -> None:
    """Write parsed answer to the traits dict."""
    traits[question.key] = parsed
