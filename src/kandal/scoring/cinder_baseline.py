"""Stage-1 baseline hard gate for cinder matching — the cost gate.

Runs FIRST, before any LLM call, so the judge only sees plausible pairs. Hard
filters here: Age (a stated Age preference is a hard cut, bilateral; else a
default sanity window), dating-intent overlap, explicit kids conflict, and
substance dealbreakers (a stated Cannabis/Drinking/Smoking preference vs the
other person's actual usage score, bilateral). Every OTHER stated preference
stays soft and is weighed by the LLM judge (see cinder_judge.py).

Pure function — no DB/API.
"""

from __future__ import annotations

from kandal.models.cinder import CinderProfile
from kandal.scoring.cinder_prefs import (
    _norm,
    _split_csv,
    stated_age_range,
    substance_dealbreakers,
)

# Used when a person did NOT list Age as a preference.
DEFAULT_AGE_SPREAD = 12

# relationship_intent values that count as dating-oriented (Friendship excluded).
_DATING_INTENTS = {"casual_dating", "relationship", "marriage"}

# wants_kids values treated as hard yes / hard no for the conflict check.
_HARD_WANTS = "wants_kids"
_HARD_NO_KIDS = "do_not_want_kids"


def _age_ok(viewer: CinderProfile, target: CinderProfile) -> bool:
    """target.age must fall in viewer's stated Age range, else viewer.age +/- spread."""
    if target.age is None:
        return True  # can't evaluate -> don't drop
    rng = stated_age_range(viewer)
    if rng is None:
        if viewer.age is None:
            return True
        rng = (viewer.age - DEFAULT_AGE_SPREAD, viewer.age + DEFAULT_AGE_SPREAD)
    return rng[0] <= target.age <= rng[1]


def _dating_intents(profile: CinderProfile) -> set[str]:
    return {_norm(t) for t in _split_csv(profile.relationship_intent)} & _DATING_INTENTS


def _intent_overlap_ok(woman: CinderProfile, man: CinderProfile) -> bool:
    w, m = _dating_intents(woman), _dating_intents(man)
    # If a side stated no dating intent at all (blank, or Friendship-only), drop it.
    if not w or not m:
        # Blank intent -> can't evaluate; only fail when a side explicitly has
        # intents but none are dating-oriented (i.e. Friendship-only).
        w_raw = {_norm(t) for t in _split_csv(woman.relationship_intent)}
        m_raw = {_norm(t) for t in _split_csv(man.relationship_intent)}
        if (w_raw and not w) or (m_raw and not m):
            return False
        return True
    return bool(w & m)


def _kids_conflict(woman: CinderProfile, man: CinderProfile) -> bool:
    a, b = _norm(woman.wants_kids or ""), _norm(man.wants_kids or "")
    return {a, b} == {_HARD_WANTS, _HARD_NO_KIDS}


def passes_baseline(woman: CinderProfile, man: CinderProfile) -> tuple[bool, dict]:
    """Return (passed, audit). audit records each gate's result for debugging."""
    age_ok = _age_ok(woman, man) and _age_ok(man, woman)
    intent_ok = _intent_overlap_ok(woman, man)
    kids_ok = not _kids_conflict(woman, man)
    # Substance dealbreakers, bilateral: her prefs vs his usage AND his vs hers.
    sub_violations = substance_dealbreakers(woman, man) + substance_dealbreakers(man, woman)
    substances_ok = not sub_violations
    audit = {
        "age_ok": age_ok,
        "intent_ok": intent_ok,
        "kids_ok": kids_ok,
        "substances_ok": substances_ok,
        "substance_violations": sub_violations,
    }
    return (age_ok and intent_ok and kids_ok and substances_ok, audit)
