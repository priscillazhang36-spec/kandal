# Testing the cinder matching algorithm

Per-woman ranked shortlists for the Cinder cohort (`cinder_profiles`: women × men),
iterated with Claude judging in-session — no Anthropic API calls.

## Pipeline recap

1. **Stage 1 — baseline gate** (`scoring/cinder_baseline.py`, the cost gate): Age
   (stated Age preference is a hard cut, bilateral; else ±`DEFAULT_AGE_SPREAD`),
   dating-intent overlap (Friendship-only excluded), explicit kids conflict, and
   **substance dealbreakers** (a stated Cannabis/Drinking/Smoking preference vs the
   other person's actual `*_score`, bilateral — see `cinder_prefs.substance_dealbreakers`).
2. **Stage 2 — LLM spark judge** (`scoring/cinder_judge.py`, the single scorer):
   reads both people, weighs MBTI heavily and against what the other wants, respects
   the ranked top-3 priorities, and scores from an imagined first-date scene.

### Deep ideal-type profiles (richer match for some women)
A cinder woman who also completed `ideal_type_discovery` is bridged to her
`ideal_types` row via `cinder_profiles.profile_id` (→ `profiles.id`). When present,
`cinder_match.load_ideal_types()` attaches her `IdealType` and the judge card gains a
**HER IDEAL TYPE** block — `pull_pattern` + `partner_traits` (positive target) and
**`break_pattern` + `icks`** (strong negatives: a man who reads as an ick or re-creates
her break pattern is heavily penalized and capped out of her top matches). Set up the
bridge by running migration `00030` + `cinder/data/cinder_profile_id_update.sql`
(currently links Sarah Mullins & Tanvi Punjani). Women without a `profile_id` use the
ordinary card unchanged.

All preferences except Age are **soft** — the judge weighs them, they don't filter.

## No-API iteration loop

```bash
pip install -e ".[dev]"   # if module imports fail, prefix commands with PYTHONPATH=src

# 1. Gather: per-woman cards + baseline-passing shortlists (no API)
PYTHONPATH=src python -m kandal.scripts.cinder_test gather --out /tmp/cinder_pairs.json
```

Gather file shape:
```json
{
  "women": { "<woman_id>": {"name": "...", "card": "<judge card>"} },
  "men":   { "<man_id>":   {"name": "...", "card": "<judge card>"} },
  "shortlists": { "<woman_id>": [ {"man_id": "...", "man_name": "..."} ] }
}
```

2. **Judge (the session work).** Dump compact views to stay under read limits, then
   Claude reads the cards + shortlists and writes `/tmp/cinder_verdicts.json`:

```json
{
  "<woman_id>__<man_id>": {
    "score": 0.0-1.0,
    "summary": "1 sentence",
    "scene": "imagined first 20 minutes",
    "reasons": ["...", "...", "..."],
    "concerns": ["...", "..."]
  }
}
```

Judge contract (matches `scoring/cinder_judge.py:_CINDER_JUDGE_SYSTEM`):
- Most pairs lack spark — most scores below 0.6; 0.8+ only when it clearly works; 0.9+ rare.
- **Weigh MBTI heavily** and cross-compare each type against what the other wants
  (her `preference_profile` + both ranked top-3s).
- Respect preference **priority** — Priority 1 outweighs Priority 3.
- Score from the imagined scene, not a checklist.

3. **Load:** rank each woman's judged men by score, assign `rank`, upsert to `cinder_matches`.

```bash
PYTHONPATH=src python -m kandal.scripts.cinder_test load \
    --pairs /tmp/cinder_pairs.json --verdicts /tmp/cinder_verdicts.json
```

## Live run (real API)

```bash
# Bound cost first with a per-woman cap, then drop it once the prompt is tuned.
PYTHONPATH=src python -m kandal.scripts.cinder_match --max-candidates-per-woman 15
PYTHONPATH=src python -m kandal.scripts.cinder_match            # full run
```

## Querying results

```sql
SELECT w.first_name AS woman, m.first_name AS man, c.rank, c.score, c.llm_summary
FROM cinder_matches c
JOIN cinder_profiles w ON w.id = c.woman_id
JOIN cinder_profiles m ON m.id = c.man_id
WHERE w.first_name = 'Sarah'
ORDER BY c.rank;
```

## Files involved

- `src/kandal/models/cinder.py` — `CinderProfile` row shape
- `src/kandal/scoring/cinder_prefs.py` — top-3 preference parser + Age extractor
- `src/kandal/scoring/cinder_baseline.py` — Stage 1
- `src/kandal/scoring/cinder_judge.py` — Stage 2 (the scorer; the test bypasses the
  API by having Claude judge inline, but the card formatter + prompt contract are shared)
- `src/kandal/scripts/cinder_match.py` — live batch runner
- `src/kandal/scripts/cinder_test.py` — gather/load no-API driver
- `supabase/migrations/00029_cinder_matches.sql` — output table
