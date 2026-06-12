"""Parse the cinder top-3 preference encoding into priority-ordered, readable form.

The `preferences` column is a comma-list of up to 3 FIELD NAMES in priority order
(e.g. "Age, Education level, Smoking"); `preference1/2/3` hold the desired VALUE
string for each, in the same order — `preference1` is the person's #1 priority.

The matching judge does the actual compatibility comparison; this module only
parses + renders the prefs for the judge card and extracts the Age range (the one
preference promoted to a hard Stage-1 filter — see cinder_baseline.py).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from kandal.models.cinder import CinderProfile

logger = logging.getLogger(__name__)

_AGE_RANGE_RE = re.compile(r"(\d+)\s*\D+?\s*(\d+)")


@dataclass
class ParsedPreference:
    rank: int  # 1 = highest priority
    field_label: str  # original label, e.g. "Education level"
    values: list[str]  # split + stripped value tokens


def _split_csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [tok.strip() for tok in s.split(",") if tok.strip()]


def _norm(s: str) -> str:
    """Lowercase, strip, collapse whitespace -> single underscores."""
    return re.sub(r"\s+", "_", s.strip().lower())


def _humanize(token: str) -> str:
    """Turn a stored code into display text: 'emotionally_intelligent' -> 'Emotionally intelligent'."""
    return token.replace("_", " ").strip().capitalize()


def _parse_age_range(s: str) -> tuple[int, int] | None:
    """'22 to 33' / '25-32' -> (22, 33). Returns None if no two ints found."""
    if not s:
        return None
    m = _AGE_RANGE_RE.search(s)
    if not m:
        return None
    lo, hi = int(m.group(1)), int(m.group(2))
    return (lo, hi) if lo <= hi else (hi, lo)


def parse_preferences(profile: CinderProfile) -> list[ParsedPreference]:
    """Zip the priority-ordered field labels with their value strings.

    Returns [] when no preferences are set. Logs + skips slots whose value is
    missing (defensive — observed data aligns cleanly).
    """
    labels = _split_csv(profile.preferences)
    if not labels:
        return []
    values = [profile.preference1, profile.preference2, profile.preference3]
    parsed: list[ParsedPreference] = []
    for i, label in enumerate(labels[:3]):
        raw_val = values[i] if i < len(values) else None
        toks = _split_csv(raw_val)
        if not toks:
            logger.warning(
                "cinder prefs: %s lists %r at priority %d but value slot is empty",
                profile.full_name or profile.id, label, i + 1,
            )
            continue
        parsed.append(ParsedPreference(rank=i + 1, field_label=label, values=toks))
    return parsed


def stated_age_range(profile: CinderProfile) -> tuple[int, int] | None:
    """Return the parsed Age range iff 'Age' is one of this person's preferences."""
    for pref in parse_preferences(profile):
        if _norm(pref.field_label) == "age":
            return _parse_age_range(", ".join(pref.values))
    return None


# --- Substance dealbreakers (Cannabis / Drinking / Smoking) --------------------
# A stated substance preference is compared against the OTHER person's actual
# usage score; if they use MORE than the preference tolerates, it's a hard
# Stage-1 dealbreaker (see cinder_baseline.py). The *_score columns are 1-based,
# 1 = lowest use.
_SUBSTANCE_ATTR = {
    "cannabis": "cannabis_score",  # 1=none, 2=socially, 3=regularly
    "drinking": "alcohol_score",   # 1=rarely/none, 2=socially, 3=regularly
    "smoking": "smoking_score",    # 1=non-smoker, 2=social, 3=smoker, 4=heavy
}
# Normalized preference phrase -> the highest usage level it still tolerates.
_SUBSTANCE_CEILING = {
    "cannabis": {"never": 1, "no": 1, "not_at_all": 1, "socially": 2,
                 "frequently": 3, "regularly": 3},
    "drinking": {"not_at_all": 1, "never": 1, "on_special_occasions": 2,
                 "socially_on_weekends": 2, "socially": 2, "most_nights": 3,
                 "frequently": 3, "regularly": 3},
    "smoking": {"non_smoker": 1, "no": 1, "never": 1, "social_smoker": 2,
                "socially": 2, "most_nights": 3, "heavy_smoker": 4},
}


def is_substance_field(field_label: str) -> bool:
    return _norm(field_label) in _SUBSTANCE_ATTR


def _substance_ceiling(field: str, values: list[str]) -> int | None:
    """Highest usage level a stated preference tolerates (max over listed phrases)."""
    table = _SUBSTANCE_CEILING[field]
    levels = [table[_norm(v)] for v in values if _norm(v) in table]
    return max(levels) if levels else None


def substance_dealbreakers(viewer: CinderProfile, target: CinderProfile) -> list[str]:
    """Violated substance dealbreakers when applying viewer's prefs to target.

    Empty list = passes. For each Cannabis/Drinking/Smoking field in the viewer's
    top-3 prefs, fail if the target's actual usage score exceeds what the
    preference tolerates. Unknown target score (None) -> skipped (can't evaluate).
    """
    violations: list[str] = []
    for pref in parse_preferences(viewer):
        field = _norm(pref.field_label)
        if field not in _SUBSTANCE_ATTR:
            continue
        ceiling = _substance_ceiling(field, pref.values)
        if ceiling is None:
            logger.warning(
                "cinder prefs: unmapped %s preference %r", field, pref.values
            )
            continue
        actual = getattr(target, _SUBSTANCE_ATTR[field], None)
        if actual is not None and actual > ceiling:
            violations.append(f"{field}(wants<={ceiling}, has={actual})")
    return violations


def render_prefs(parsed: list[ParsedPreference]) -> str:
    """One-line priority-ordered rendering for the judge card."""
    if not parsed:
        return "(none stated)"
    return " | ".join(
        f"Priority {p.rank} — {p.field_label}: {', '.join(p.values)}" for p in parsed
    )
