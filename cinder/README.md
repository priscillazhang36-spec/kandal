# Cinder — guest matching (June 19 event)

Self-contained collection of everything for the Cinder cohort: 8 registered women ×
121 available men, matched into per-woman ranked shortlists.

> **Note on the code files:** `models/`, `scoring/`, `scripts/`, `migrations/`, `tests/`
> here are **copies** for convenience. The live, importable source of truth lives in the
> package (`src/kandal/...`, `supabase/migrations/`, `tests/`, `docs/`). Edit those, not
> these copies — running `python -m kandal.scripts.cinder_match` uses the package versions.

## Contents

```
cinder/
├── data/                       # deliverables (moved here)
│   ├── cinder_shortlists.csv   # all 8 women × top-10 men, ranked + rationale
│   ├── cinder_top3_men.csv     # the 17 unique men appearing in any woman's top 3
│   ├── women_seed.sql          # 8 registered women seed
│   └── men_seed.sql            # 121 available men seed
├── models/cinder.py            # CinderProfile row model
├── scoring/
│   ├── cinder_prefs.py         # top-3 priority preference parser
│   ├── cinder_baseline.py      # Stage 1 hard gate (age / intent / kids)
│   └── cinder_judge.py         # Stage 2 LLM spark judge (the scorer)
├── scripts/
│   ├── cinder_match.py         # live batch runner
│   ├── cinder_test.py          # no-API gather/load driver
│   └── ingest_cinder.py        # TSV -> cinder_profiles loader
├── migrations/
│   ├── 00028_cinder_profiles.sql
│   └── 00029_cinder_matches.sql
├── tests/test_cinder_prefs.py
└── docs/testing_cinder_match.md
```

## Pipeline (recap)
1. **Stage 1 — baseline gate** (cost gate): Age (stated Age preference = hard cut,
   bilateral; else ±12), dating-intent overlap (Friendship-only excluded), kids conflict.
2. **Stage 2 — LLM spark judge** (single scorer): imagines the first date and scores
   spark-first; MBTI weighted heavily and cross-checked against what each person wants;
   the stated top-3 preferences weighed in priority order (P1 > P2 > P3).

Output: `cinder_matches` (per-woman ranked shortlists). The CSVs in `data/` are the
exported results.

## Reproduce the CSVs
The shortlists were produced via the no-API in-session flow (Opus 4.8 as judge) — see
`docs/testing_cinder_match.md`. Live run: `python -m kandal.scripts.cinder_match`.

_Raw input `women_seed.tsv` was left in `data/cinder/` (it's a source export, not a
deliverable)._
