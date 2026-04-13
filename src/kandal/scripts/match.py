"""Batch matching: 3-stage pipeline.

Stage 1 — Hard filters (dealbreakers): age, gender, distance, ethnicity, etc.
Stage 2 — Coarse ranker: weighted dimension score + embeddings (cheap).
Stage 3 — LLM judge: Claude reads both narratives + traits for the top-K
          finalists per user and returns a structured verdict.

Run: python -m kandal.scripts.match
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

from kandal.core.supabase import get_supabase
from kandal.models.preferences import Preferences
from kandal.models.profile import Profile
from kandal.scoring import compute_verdict, passes_dealbreakers, score_compatibility
from kandal.scoring.llm_judge import judge_pair

logger = logging.getLogger(__name__)

# How many top-coarse candidates per user advance to the LLM judge.
# Higher = more accurate, more expensive (linear in cost).
TOP_K_PER_USER = 20

# Minimum LLM verdict score required to be written as a match.
LLM_MATCH_THRESHOLD = 0.7

# When the dealbreaker-passing pool is this small, skip the coarse-rank cutoff
# and send every passing pair straight to the LLM judge. Cheap when N is tiny.
SMALL_POOL_BYPASS = 25


def _load_users():
    client = get_supabase()
    profiles_resp = client.table("profiles").select("*").eq("is_active", True).execute()
    prefs_resp = client.table("preferences").select("*").execute()
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


def _stage2_coarse_rank(pairs, profiles, prefs):
    """Score every passing pair from both perspectives. Returns dict[pair] -> data."""
    scored = {}
    for a, b in pairs:
        pa, pb = profiles[a], profiles[b]
        pra, prb = prefs[a], prefs[b]
        result_a = score_compatibility(pa, pra, pb, prb, perspective_weights=pra.dimension_weights)
        result_b = score_compatibility(pa, pra, pb, prb, perspective_weights=prb.dimension_weights)
        coarse = round((result_a.total_score + result_b.total_score) / 2, 4)
        verdict = compute_verdict(result_a, result_b, pra.selectivity, prb.selectivity)
        scored[(a, b)] = {
            "coarse_score": coarse,
            "result_a": result_a,
            "result_b": result_b,
            "coarse_verdict": verdict,
        }
    return scored


def _select_finalists(scored: dict, k: int = TOP_K_PER_USER) -> set[tuple[str, str]]:
    """For each user, keep their top-K coarsely-ranked partners. Union across users."""
    by_user: dict[str, list[tuple[float, tuple[str, str]]]] = defaultdict(list)
    for pair, data in scored.items():
        a, b = pair
        by_user[a].append((data["coarse_score"], pair))
        by_user[b].append((data["coarse_score"], pair))

    finalists: set[tuple[str, str]] = set()
    for _, ranked in by_user.items():
        ranked.sort(reverse=True)
        for _, pair in ranked[:k]:
            finalists.add(pair)
    return finalists


def _stage3_llm_judge(finalists, scored, profiles, prefs):
    """Call Claude on each finalist pair. Returns dict[pair] -> LLMVerdict."""
    verdicts = {}
    for i, (a, b) in enumerate(finalists, 1):
        v = judge_pair(
            profiles[a], prefs[a],
            profiles[b], prefs[b],
            coarse_score=scored[(a, b)]["coarse_score"],
        )
        if v is not None:
            verdicts[(a, b)] = v
        if i % 25 == 0:
            logger.info("LLM-judged %d/%d finalists", i, len(finalists))
    return verdicts


def run_batch():
    profiles, prefs = _load_users()
    user_count = sum(1 for uid in profiles if uid in prefs)

    # Stage 1
    passing = _stage1_filter(profiles, prefs)
    logger.info("Stage 1: %d pairs passed dealbreakers", len(passing))

    # Stage 2 — always compute coarse scores (used for breakdown storage),
    # but skip the top-K cutoff when the pool is small enough to LLM-judge fully.
    scored = _stage2_coarse_rank(passing, profiles, prefs)
    if len(passing) < SMALL_POOL_BYPASS:
        finalists = set(scored.keys())
        logger.info(
            "Stage 2 cutoff skipped: %d pairs < %d threshold — judging all",
            len(passing), SMALL_POOL_BYPASS,
        )
    else:
        finalists = _select_finalists(scored, TOP_K_PER_USER)
        logger.info("Stage 2: %d finalists selected (top-%d per user)", len(finalists), TOP_K_PER_USER)

    # Stage 3
    verdicts = _stage3_llm_judge(finalists, scored, profiles, prefs)
    logger.info("Stage 3: %d LLM verdicts returned", len(verdicts))

    now_iso = datetime.now(timezone.utc).isoformat()
    matches_to_insert = []
    for pair, v in verdicts.items():
        if v.score < LLM_MATCH_THRESHOLD:
            continue
        a, b = pair
        data = scored[pair]
        matches_to_insert.append({
            "profile_a_id": a,
            "profile_b_id": b,
            "score": v.score,
            "coarse_score": data["coarse_score"],
            "llm_score": v.score,
            "llm_summary": v.summary,
            "llm_reasons": v.reasons,
            "llm_concerns": v.concerns,
            "judged_at": now_iso,
            "verdict": "match",
            "breakdown": {
                "perspective_a": {d.dimension: d.score for d in data["result_a"].breakdown},
                "perspective_b": {d.dimension: d.score for d in data["result_b"].breakdown},
                "weights_a": {d.dimension: d.weight for d in data["result_a"].breakdown},
                "weights_b": {d.dimension: d.weight for d in data["result_b"].breakdown},
            },
        })

    if matches_to_insert:
        get_supabase().table("matches").upsert(
            matches_to_insert, on_conflict="profile_a_id,profile_b_id"
        ).execute()

    print(
        f"Users: {user_count} | "
        f"Stage1 pairs: {len(passing)} | "
        f"Stage2 finalists: {len(finalists)} | "
        f"Stage3 LLM verdicts: {len(verdicts)} | "
        f"Matches written (≥{LLM_MATCH_THRESHOLD}): {len(matches_to_insert)}"
    )
    return {
        "users_processed": user_count,
        "stage1_passing_pairs": len(passing),
        "stage2_finalists": len(finalists),
        "stage3_verdicts": len(verdicts),
        "matches_found": len(matches_to_insert),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_batch()
