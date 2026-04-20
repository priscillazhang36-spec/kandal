"""Batch matching: 2-stage pipeline.

Stage 1 — Hard filters (dealbreakers): age, gender, distance, relationship type.
Stage 2 — LLM judge: Claude reads both narratives + traits for every passing
          pair and returns a structured verdict.

Run: python -m kandal.scripts.match
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from itertools import combinations

from kandal.core.supabase import get_supabase
from kandal.models.preferences import Preferences
from kandal.models.profile import Profile
from kandal.scoring import passes_dealbreakers
from kandal.scoring.llm_judge import judge_pair

logger = logging.getLogger(__name__)

# Minimum LLM verdict score required to be written as a match.
LLM_MATCH_THRESHOLD = 0.7


def _load_users(profiles_table: str = "profiles", prefs_table: str = "preferences"):
    client = get_supabase()
    profiles_resp = client.table(profiles_table).select("*").eq("is_active", True).execute()
    prefs_resp = client.table(prefs_table).select("*").execute()
    profiles = {p["id"]: Profile(**p) for p in profiles_resp.data}
    prefs = {p["profile_id"]: Preferences(**p) for p in prefs_resp.data}
    return profiles, prefs


def _stage1_filter(profiles, prefs) -> list[tuple[str, str]]:
    """Return all user-ID pairs that pass hard dealbreakers."""
    ids = sorted(uid for uid in profiles if uid in prefs)
    passing: list[tuple[str, str]] = []
    for a, b in combinations(ids, 2):
        if passes_dealbreakers(profiles[a], prefs[a], profiles[b], prefs[b]):
            passing.append((a, b))
    return passing


def _stage2_llm_judge(pairs, profiles, prefs):
    """Call Claude on each passing pair. Returns dict[pair] -> LLMVerdict."""
    verdicts = {}
    for i, (a, b) in enumerate(pairs, 1):
        v = judge_pair(profiles[a], prefs[a], profiles[b], prefs[b])
        if v is not None:
            verdicts[(a, b)] = v
        if i % 25 == 0:
            logger.info("LLM-judged %d/%d pairs", i, len(pairs))
    return verdicts


def run_batch(
    profiles_table: str = "profiles",
    prefs_table: str = "preferences",
    matches_table: str = "matches",
):
    profiles, prefs = _load_users(profiles_table, prefs_table)
    user_count = sum(1 for uid in profiles if uid in prefs)

    passing = _stage1_filter(profiles, prefs)
    logger.info("Stage 1: %d pairs passed dealbreakers", len(passing))

    verdicts = _stage2_llm_judge(passing, profiles, prefs)
    logger.info("Stage 2: %d LLM verdicts returned", len(verdicts))

    now_iso = datetime.now(timezone.utc).isoformat()
    matches_to_insert = []
    for (a, b), v in verdicts.items():
        if v.score < LLM_MATCH_THRESHOLD:
            continue
        matches_to_insert.append({
            "profile_a_id": a,
            "profile_b_id": b,
            "score": v.score,
            "llm_summary": v.summary,
            "llm_reasons": v.reasons,
            "llm_concerns": v.concerns,
            "judged_at": now_iso,
            "verdict": "match",
        })

    if matches_to_insert:
        get_supabase().table(matches_table).upsert(
            matches_to_insert, on_conflict="profile_a_id,profile_b_id"
        ).execute()

    print(
        f"Users: {user_count} | "
        f"Stage1 pairs: {len(passing)} | "
        f"Stage2 LLM verdicts: {len(verdicts)} | "
        f"Matches written (≥{LLM_MATCH_THRESHOLD}): {len(matches_to_insert)}"
    )
    return {
        "users_processed": user_count,
        "stage1_passing_pairs": len(passing),
        "stage2_verdicts": len(verdicts),
        "matches_found": len(matches_to_insert),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_batch()
