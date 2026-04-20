# Testing the matching algorithm

End-to-end test of the 2-stage matching pipeline (dealbreaker filter + LLM judge) against synthetic profiles in the `test_*` tables. Supports comparing verdicts across models (e.g. Opus vs Haiku, or variants of the same model with different prompts) on the same pair set.

## Data model

- **`test_profiles` / `test_preferences`** — mirror the prod columns the Pydantic models read.
- **`test_matches`** — one row per `(profile pair × model)`, keyed by `(profile_a_id, profile_b_id, model)`. Stores every pair (including dealbreaker-failed ones) so the same run captures filter reasons alongside verdicts.
  - `pass_dealbreaker` — stage 1 result
  - `score`, `is_matched` — stage 2 result (NULL for failed dealbreakers)
  - `llm_summary`, `llm_reasons`, `llm_concerns` — judge verdict
  - `model` — tag for the judging model (or prompt variant — tag creatively)

Schema: `supabase/migrations/00015_test_tables.sql`, `00016_test_matches_all_pairs.sql`.

## Prerequisites

```bash
pip install -e ".[dev]"
```

If `python -m kandal.*` fails with `ModuleNotFoundError`, the editable `.pth` isn't being picked up — prefix commands with `PYTHONPATH=src`.

## Flow at a glance

1. **Seed** — have profiles in `test_profiles` / `test_preferences`. Either wipe-and-reinsert, or append more profiles to an existing set.
2. **Gather pairs** — for every pair of profiles in the tables, compute `pass_dealbreaker` and format each person's judge card. Dump to a JSON file.
3. **Judge** — Claude in the current session reads the gather file and emits a verdicts JSON file.
4. **Load** — write all pairs + verdicts to `test_matches` tagged with `--model`.
5. **Repeat 3–4** under a different model tag to compare.

No Anthropic API calls are made — Claude in the session is the judge, saving cost.

## Seeding profiles

Two valid modes:

- **Wipe-and-reinsert** (the current `synthetic_test.py gather` behavior): good for fresh runs against a curated archetype set like `src/kandal/scripts/synthetic_profiles.py`.
- **Additive**: just insert more rows into `test_profiles` / `test_preferences` without wiping. Useful when you want to extend the pool without losing prior data. Skip the insert half of `gather` and call the pair-computation step directly, or adapt the script.

When in doubt about which mode to use for a given iteration, ask before running — `gather` wipes `test_matches` too, so previous model runs are lost.

## Gather — compute pairs + judge cards

Current implementation wipes `test_*`, inserts profiles from `synthetic_profiles.py`, then writes the gather file:

```bash
PYTHONPATH=src python -m kandal.scripts.synthetic_test gather --out /tmp/kandal_pairs.json
```

Gather file shape:
```json
{
  "cards": { "<uuid>": {"name": "...", "card": "<formatted judge card>"} },
  "pairs": [ {"a_id": "...", "b_id": "...", "a_name": "...", "b_name": "...", "pass_dealbreaker": true/false} ]
}
```

For additive / non-wipe runs, skip or modify the clear-and-insert step; the pair computation + card formatting logic is the reusable core.

## Judging (this is the session work)

Gather files can easily exceed Claude's read limit. Dump compact views first:

```bash
python - <<'EOF'
import json
d = json.load(open('/tmp/kandal_pairs.json'))
with open('/tmp/kandal_cards.txt', 'w') as f:
    for uid, c in d['cards'].items():
        f.write(f"===== {c['name']} (id={uid}) =====\n{c['card']}\n\n")
with open('/tmp/kandal_passing.txt', 'w') as f:
    for p in d['pairs']:
        if p['pass_dealbreaker']:
            f.write(f"{p['a_name']} + {p['b_name']}  |  {p['a_id']}  |  {p['b_id']}\n")
EOF
```

Claude reads the cards + passing list and writes `/tmp/kandal_verdicts_<tag>.json`:

```json
{
  "<a_id>__<b_id>": {
    "score": 0.0-1.0,
    "summary": "1-2 sentences",
    "reasons": ["phrase", "phrase", "phrase"],
    "concerns": ["phrase", "phrase"]
  }
}
```

**Key ordering**: `{a_id}__{b_id}` in the exact order from `/tmp/kandal_passing.txt`. The load step does not reorder — reversed keys report as missing verdicts.

**Judge contract** (matches `src/kandal/scoring/llm_judge.py:_JUDGE_SYSTEM`):
- Most pairs are not great fits — most scores below 0.6
- 0.8+ reserved for pairs clearly working
- 0.9+ reserved for rare standouts
- Be honest about concerns even when scoring high

## Load

```bash
PYTHONPATH=src python -m kandal.scripts.synthetic_test load \
    --pairs /tmp/kandal_pairs.json \
    --verdicts /tmp/kandal_verdicts_<tag>.json \
    --model <model-tag>
```

Writes every pair in the gather file (passing + failing). If rows already exist for this `(pair × model)`, the upsert overwrites them.

## Comparing models

Switch the Claude Code session via `/model`, re-judge using the *same* gather file, write a new verdicts JSON, and `load` with a different `--model` tag.

**Do not re-run `gather` between models** — it wipes `test_matches`, deleting prior verdicts. If you need fresh dealbreakers (e.g. after changing the filter), run `gather` once and re-judge across all models.

## Querying results

### Top matches for one model
```sql
SELECT pa.name || ' + ' || pb.name AS pair, score, llm_summary
FROM test_matches m
JOIN test_profiles pa ON pa.id = m.profile_a_id
JOIN test_profiles pb ON pb.id = m.profile_b_id
WHERE m.model = '<model-tag>' AND m.is_matched
ORDER BY score DESC;
```

### Pairs where two models disagreed
```sql
WITH a AS (
    SELECT profile_a_id, profile_b_id, score, (score > 0.7) AS matched
    FROM test_matches WHERE model = '<tag-a>' AND pass_dealbreaker
),
b AS (
    SELECT profile_a_id, profile_b_id, score, (score > 0.7) AS matched
    FROM test_matches WHERE model = '<tag-b>' AND pass_dealbreaker
)
SELECT pa.name AS a, pb.name AS b,
       ROUND(a.score::numeric, 2) AS score_a,
       ROUND(b.score::numeric, 2) AS score_b,
       ROUND((a.score - b.score)::numeric, 2) AS delta
FROM a JOIN b USING (profile_a_id, profile_b_id)
JOIN test_profiles pa ON pa.id = a.profile_a_id
JOIN test_profiles pb ON pb.id = a.profile_b_id
WHERE a.matched <> b.matched
ORDER BY ABS(a.score - b.score) DESC;
```

### Why a specific pair didn't match
```sql
SELECT model, pass_dealbreaker, score, is_matched, llm_summary, llm_concerns
FROM test_matches
WHERE profile_a_id = '<uuid>' AND profile_b_id = '<uuid>';
```

## Iterating

When changing scoring code (dealbreakers, judge prompt, threshold):
1. Seed / gather once to refresh `test_matches` + pair-level dealbreakers.
2. Judge + `load` under one or more `--model` tags. Tag creatively for prompt variants (e.g. `claude-opus-4-7-strict`, `claude-opus-4-7-loose`).
3. Compare rows via SQL.

## Files involved

- `src/kandal/scripts/synthetic_test.py` — driver with `gather` / `load` subcommands
- `src/kandal/scripts/synthetic_profiles.py` — default archetype profile set
- `src/kandal/scoring/dealbreakers.py` — stage 1
- `src/kandal/scoring/llm_judge.py` — stage 2 (the prod judge; the synthetic test bypasses the API call by having Claude judge inline, but the prompt + card formatter are shared)
- `supabase/migrations/00015_test_tables.sql`, `00016_test_matches_all_pairs.sql` — test schema
