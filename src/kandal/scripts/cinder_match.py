"""Cinder matching: per-woman ranked shortlists of men.

Two stages, pivoted per woman (bipartite woman x man, not all-pairs):
  Stage 1 — baseline hard gate (age / dating intent / kids). The cost gate:
            the LLM only runs on men who pass.
  Stage 2 — LLM spark judge scores ALL aspects of each passing pair (MBTI-heavy,
            priority-weighted). Rank by score, write the top-N to cinder_matches.

Run: python -m kandal.scripts.cinder_match [--top-n N] [--no-api]
                                           [--max-candidates-per-woman K]
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from kandal.core.supabase import get_supabase
from kandal.models.cinder import CinderProfile
from kandal.models.ideal_type import IdealType
from kandal.scoring.cinder_baseline import passes_baseline
from kandal.scoring.cinder_judge import judge_pair_cinder

logger = logging.getLogger(__name__)

TOP_N_DEFAULT = 10
PROFILES_TABLE = "cinder_profiles"
MATCHES_TABLE = "cinder_matches"


def _load_cinder(table: str = PROFILES_TABLE) -> tuple[list[CinderProfile], list[CinderProfile]]:
    client = get_supabase()
    rows = client.table(table).select("*").execute().data
    women, men = [], []
    for row in rows:
        p = CinderProfile(**row)
        (women if p.gender == "woman" else men).append(p)
    return women, men


def load_ideal_types(women: list[CinderProfile]) -> dict[str, IdealType]:
    """Map woman.id -> her completed IdealType (women bridged via profile_id).

    Cinder women who finished ideal_type_discovery have a `profile_id` pointing at
    their ideal_types row. Returns {} when none are linked.
    """
    pid_to_wid = {str(w.profile_id): str(w.id) for w in women if w.profile_id}
    if not pid_to_wid:
        return {}
    rows = (
        get_supabase().table("ideal_types").select("*")
        .in_("profile_id", list(pid_to_wid)).eq("stage", "complete").execute().data
    )
    newest: dict[str, dict] = {}  # keep the freshest complete row per profile_id
    for r in rows:
        pid = str(r["profile_id"])
        if pid not in newest or (r.get("updated_at") or "") > (newest[pid].get("updated_at") or ""):
            newest[pid] = r
    out: dict[str, IdealType] = {}
    for pid, r in newest.items():
        data = {k: v for k, v in r.items() if k in IdealType.model_fields}
        out[pid_to_wid[pid]] = IdealType(**data)
    return out


def _build_row(woman, man, rank, verdict, now_iso) -> dict:
    return {
        "woman_id": str(woman.id),
        "man_id": str(man.id),
        "rank": rank,
        "score": verdict.score if verdict else None,
        "llm_summary": verdict.summary if verdict else None,
        "llm_scene": verdict.scene if verdict else None,
        "llm_reasons": verdict.reasons if verdict else [],
        "llm_concerns": verdict.concerns if verdict else [],
        "passed_baseline": True,
        "judged_at": now_iso if verdict else None,
    }


def run(
    top_n: int = TOP_N_DEFAULT,
    use_api: bool = True,
    max_candidates_per_woman: int | None = None,
    profiles_table: str = PROFILES_TABLE,
    matches_table: str = MATCHES_TABLE,
):
    women, men = _load_cinder(profiles_table)
    ideal_types = load_ideal_types(women)
    logger.info("Loaded %d women, %d men (%d with ideal-type profiles)",
                len(women), len(men), len(ideal_types))

    now_iso = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    total_judged = 0

    for woman in women:
        ideal = ideal_types.get(str(woman.id))
        passing = [m for m in men if passes_baseline(woman, m)[0]]
        if max_candidates_per_woman is not None:
            passing = passing[:max_candidates_per_woman]

        judged = []
        for man in passing:
            verdict = judge_pair_cinder(woman, man, ideal_type=ideal) if use_api else None
            if use_api and verdict is None:
                continue  # parse/call failure — skip rather than write a null match
            judged.append((man, verdict))
        total_judged += len(judged)

        # Rank by LLM score (desc). When not using the API, order is undefined —
        # leave as baseline order so the test harness can fill scores later.
        judged.sort(key=lambda t: (t[1].score if t[1] else 0.0), reverse=True)

        for rank, (man, verdict) in enumerate(judged[:top_n], start=1):
            rows.append(_build_row(woman, man, rank, verdict, now_iso))

        logger.info(
            "%s: %d passed baseline, %d judged, %d written",
            woman.full_name, len(passing), len(judged), min(len(judged), top_n),
        )

    if rows:
        get_supabase().table(matches_table).upsert(
            rows, on_conflict="woman_id,man_id"
        ).execute()

    print(
        f"Women: {len(women)} | Men: {len(men)} | "
        f"Pairs judged: {total_judged} | Match rows written: {len(rows)}"
    )
    return {
        "women": len(women),
        "men": len(men),
        "pairs_judged": total_judged,
        "matches_written": len(rows),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=TOP_N_DEFAULT,
                        help="Rows written per woman (her shortlist length)")
    parser.add_argument("--no-api", action="store_true",
                        help="Skip LLM calls (writes nothing; use cinder_test for no-API flow)")
    parser.add_argument("--max-candidates-per-woman", type=int, default=None,
                        help="Cap baseline-passing men judged per woman (cost backstop)")
    args = parser.parse_args()
    run(
        top_n=args.top_n,
        use_api=not args.no_api,
        max_candidates_per_woman=args.max_candidates_per_woman,
    )


if __name__ == "__main__":
    main()
