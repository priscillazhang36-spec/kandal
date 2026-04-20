"""Synthetic matching test driver — two-phase, no-API flow.

Phase 1 (gather): clear + insert synthetic profiles, compute dealbreakers for
every C(20,2) pair, and write each profile's judge card + pair results to a
JSON file.

[Between phases] Claude reads the gather file and writes a verdicts JSON file
containing {"<a_id>__<b_id>": {score, summary, reasons, concerns}} for every
pair that passed dealbreakers.

Phase 2 (load): read gather + verdicts JSON, write all pairs (passing & failing)
to test_matches tagged with --model.

Typical flow:
  python -m kandal.scripts.synthetic_test gather --out /tmp/kandal_pairs.json
  # (Claude emits /tmp/kandal_verdicts_opus.json)
  python -m kandal.scripts.synthetic_test load \\
      --pairs /tmp/kandal_pairs.json \\
      --verdicts /tmp/kandal_verdicts_opus.json \\
      --model claude-opus-4-7
  # Switch the session to Haiku, emit /tmp/kandal_verdicts_haiku.json, rerun
  # load with --model claude-haiku-4-5-20251001.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from itertools import combinations

from kandal.core.supabase import get_supabase
from kandal.scoring import passes_dealbreakers
from kandal.scoring.llm_judge import _format_person
from kandal.scripts.match import LLM_MATCH_THRESHOLD, _load_users
from kandal.scripts.synthetic_profiles import PROFILES

logger = logging.getLogger(__name__)

PROFILES_TABLE = "test_profiles"
PREFS_TABLE = "test_preferences"
MATCHES_TABLE = "test_matches"

_NEVER_MATCH = "00000000-0000-0000-0000-000000000000"


def _clear_test_tables() -> None:
    client = get_supabase()
    client.table(MATCHES_TABLE).delete().neq("id", _NEVER_MATCH).execute()
    client.table(PREFS_TABLE).delete().neq("id", _NEVER_MATCH).execute()
    client.table(PROFILES_TABLE).delete().neq("id", _NEVER_MATCH).execute()


def _insert_profiles() -> None:
    client = get_supabase()
    profile_rows = [p["profile"] for p in PROFILES]
    prefs_rows = [p["prefs"] for p in PROFILES]
    client.table(PROFILES_TABLE).insert(profile_rows).execute()
    client.table(PREFS_TABLE).insert(prefs_rows).execute()


def cmd_gather(args) -> None:
    print("Clearing test tables...")
    _clear_test_tables()
    print(f"Inserting {len(PROFILES)} synthetic profiles...")
    _insert_profiles()

    profiles, prefs = _load_users(PROFILES_TABLE, PREFS_TABLE)
    assert len(profiles) == len(PROFILES), f"Expected {len(PROFILES)} profiles, got {len(profiles)}"

    ids = sorted(profiles.keys())
    cards = {
        uid: {
            "name": profiles[uid].name,
            "card": _format_person(profiles[uid].name or uid, profiles[uid], prefs[uid]),
        }
        for uid in ids
    }

    all_pairs = list(combinations(ids, 2))
    pairs = []
    for a, b in all_pairs:
        pairs.append({
            "a_id": a,
            "b_id": b,
            "a_name": profiles[a].name,
            "b_name": profiles[b].name,
            "pass_dealbreaker": passes_dealbreakers(profiles[a], prefs[a], profiles[b], prefs[b]),
        })

    passing = sum(1 for p in pairs if p["pass_dealbreaker"])
    with open(args.out, "w") as f:
        json.dump({"cards": cards, "pairs": pairs}, f, indent=2)
    print(f"Wrote {len(pairs)} pairs ({passing} passed dealbreakers) + {len(cards)} cards -> {args.out}")


def cmd_load(args) -> None:
    with open(args.pairs) as f:
        gather = json.load(f)
    with open(args.verdicts) as f:
        verdicts = json.load(f)

    rows = []
    now_iso = datetime.now(timezone.utc).isoformat()
    missing = []
    for p in gather["pairs"]:
        key = f"{p['a_id']}__{p['b_id']}"
        row = {
            "profile_a_id": p["a_id"],
            "profile_b_id": p["b_id"],
            "model": args.model,
            "pass_dealbreaker": p["pass_dealbreaker"],
            "score": None,
            "is_matched": False,
            "llm_summary": None,
            "llm_reasons": [],
            "llm_concerns": [],
            "judged_at": None,
        }
        if p["pass_dealbreaker"]:
            v = verdicts.get(key)
            if v is None:
                missing.append(key)
                rows.append(row)
                continue
            score = float(v["score"])
            row.update({
                "score": score,
                "is_matched": score >= LLM_MATCH_THRESHOLD,
                "llm_summary": v.get("summary", ""),
                "llm_reasons": v.get("reasons", []),
                "llm_concerns": v.get("concerns", []),
                "judged_at": now_iso,
            })
        rows.append(row)

    if missing:
        raise SystemExit(
            f"Missing verdicts for {len(missing)} passing pair(s); first few: {missing[:3]}"
        )

    get_supabase().table(MATCHES_TABLE).upsert(
        rows, on_conflict="profile_a_id,profile_b_id,model"
    ).execute()

    matched = sum(1 for r in rows if r["is_matched"])
    judged = sum(1 for r in rows if r["score"] is not None)
    print(f"Wrote {len(rows)} rows to {MATCHES_TABLE} "
          f"(model={args.model}, judged={judged}, matched={matched})")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gather", help="Clear tables, insert profiles, write pair cards + dealbreakers")
    g.add_argument("--out", default="/tmp/kandal_pairs.json")
    g.set_defaults(func=cmd_gather)

    l = sub.add_parser("load", help="Write all pairs + verdicts to test_matches tagged with --model")
    l.add_argument("--pairs", default="/tmp/kandal_pairs.json")
    l.add_argument("--verdicts", required=True)
    l.add_argument("--model", required=True)
    l.set_defaults(func=cmd_load)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
