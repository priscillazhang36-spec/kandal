"""Cinder matching test driver — two-phase, no-API flow (mirrors synthetic_test).

Phase 1 (gather): load the seeded cinder_profiles, run the Stage-1 baseline gate
per woman, and write each person's judge card + per-woman baseline-passing lists
to a JSON file. No profiles are inserted (cinder rows are already seeded).

[Between phases] Claude in the session reads the gather file and writes a verdicts
JSON: {"<woman_id>__<man_id>": {score, summary, scene, reasons, concerns}} for
every shortlisted pair. No Anthropic API calls — Claude judges inline.

Phase 2 (load): read gather + verdicts, rank each woman's men by score, assign
rank, and upsert into cinder_matches.

  python -m kandal.scripts.cinder_test gather --out /tmp/cinder_pairs.json
  # (Claude emits /tmp/cinder_verdicts.json)
  python -m kandal.scripts.cinder_test load \\
      --pairs /tmp/cinder_pairs.json --verdicts /tmp/cinder_verdicts.json
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone

from kandal.core.supabase import get_supabase
from kandal.scoring.cinder_baseline import passes_baseline
from kandal.scoring.cinder_judge import _format_person_cinder
from kandal.scripts.cinder_match import (
    MATCHES_TABLE,
    TOP_N_DEFAULT,
    _load_cinder,
    load_ideal_types,
)

logger = logging.getLogger(__name__)


def cmd_gather(args) -> None:
    women, men = _load_cinder()
    ideal_types = load_ideal_types(women)
    women_cards, men_cards, shortlists = {}, {}, {}

    for w in women:
        wid = str(w.id)
        women_cards[wid] = {
            "name": w.full_name,
            "has_ideal_type": wid in ideal_types,
            "card": _format_person_cinder(
                w.full_name or wid, w, is_woman=True, ideal_type=ideal_types.get(wid)
            ),
        }
        passing = [m for m in men if passes_baseline(w, m)[0]]
        shortlists[wid] = [{"man_id": str(m.id), "man_name": m.full_name} for m in passing]
        for m in passing:
            mid = str(m.id)
            if mid not in men_cards:
                men_cards[mid] = {
                    "name": m.full_name,
                    "card": _format_person_cinder(m.full_name or mid, m, is_woman=False),
                }

    with open(args.out, "w") as f:
        json.dump(
            {"women": women_cards, "men": men_cards, "shortlists": shortlists},
            f, indent=2,
        )
    total = sum(len(v) for v in shortlists.values())
    print(f"Wrote {len(women_cards)} women, {len(men_cards)} men, "
          f"{total} shortlisted pairs -> {args.out}")
    if ideal_types:
        print(f"  deep ideal-type profiles attached: "
              f"{', '.join(women_cards[w]['name'] for w in ideal_types)}")
    for wid, lst in shortlists.items():
        print(f"  {women_cards[wid]['name']}: {len(lst)} passed baseline")


def cmd_load(args) -> None:
    with open(args.pairs) as f:
        gather = json.load(f)
    with open(args.verdicts) as f:
        verdicts = json.load(f)

    now_iso = datetime.now(timezone.utc).isoformat()
    rows, missing = [], []

    for wid, lst in gather["shortlists"].items():
        judged = []
        for entry in lst:
            mid = entry["man_id"]
            v = verdicts.get(f"{wid}__{mid}")
            if v is None:
                missing.append(f"{wid}__{mid}")
                continue
            judged.append((mid, v))
        judged.sort(key=lambda t: float(t[1]["score"]), reverse=True)
        for rank, (mid, v) in enumerate(judged[: args.top_n], start=1):
            rows.append({
                "woman_id": wid,
                "man_id": mid,
                "rank": rank,
                "score": float(v["score"]),
                "llm_summary": v.get("summary", ""),
                "llm_scene": v.get("scene", ""),
                "llm_reasons": v.get("reasons", []),
                "llm_concerns": v.get("concerns", []),
                "passed_baseline": True,
                "judged_at": now_iso,
            })

    if missing:
        raise SystemExit(
            f"Missing verdicts for {len(missing)} shortlisted pair(s); first few: {missing[:3]}"
        )

    if rows:
        get_supabase().table(args.table).upsert(
            rows, on_conflict="woman_id,man_id"
        ).execute()
    print(f"Wrote {len(rows)} ranked rows to {args.table}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gather", help="Write per-woman cards + baseline-passing shortlists")
    g.add_argument("--out", default="/tmp/cinder_pairs.json")
    g.set_defaults(func=cmd_gather)

    l = sub.add_parser("load", help="Rank verdicts per woman and upsert into cinder_matches")
    l.add_argument("--pairs", default="/tmp/cinder_pairs.json")
    l.add_argument("--verdicts", required=True)
    l.add_argument("--top-n", type=int, default=TOP_N_DEFAULT)
    l.add_argument("--table", default=MATCHES_TABLE)
    l.set_defaults(func=cmd_load)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
