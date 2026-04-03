# Plan: Dynamic Adaptive Matching + Scalable Pipeline

## Context

Kandal's current matching system has two problems:

1. **Static profiling**: A fixed 10-question multiple-choice questionnaire produces the same experience for every user. A human matchmaker would adapt questions based on responses and the available pool.
2. **O(n^2) scaling**: The batch pipeline (`match.py`) enumerates all user pairs via `itertools.combinations()`. At 10k users = 50M pairs, this takes ~1.4 hours single-threaded and risks OOM (12.5GB match accumulation). At 100k users it breaks entirely.

**Goal**: Replace the static questionnaire with an LLM-driven adaptive profiler (Claude), and replace the O(n^2) batch with DB-level candidate generation using pgvector + spatial indexing.

---

## Phase 0: Database Migration

Add columns, indexes, and tables that all later phases depend on. Pure SQL, no app code changes.

**New file**: `supabase/migrations/00003_scalable_matching.sql`

```sql
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;         -- pgvector for ANN search
CREATE EXTENSION IF NOT EXISTS cube;           -- for earthdistance
CREATE EXTENSION IF NOT EXISTS earthdistance;  -- for ll_to_earth / earth_box

-- Profile extensions
ALTER TABLE profiles ADD COLUMN narrative TEXT;
ALTER TABLE profiles ADD COLUMN narrative_embedding vector(1024);  -- Voyage AI voyage-3-lite
ALTER TABLE profiles ADD COLUMN profile_version INTEGER DEFAULT 1;
ALTER TABLE profiles ADD COLUMN embedding_version INTEGER DEFAULT 0;
ALTER TABLE profiles ADD COLUMN last_significant_change TIMESTAMPTZ DEFAULT now();

-- Indexes for candidate generation
CREATE INDEX idx_profiles_embedding ON profiles
  USING ivfflat (narrative_embedding vector_cosine_ops) WITH (lists = 100)
  WHERE narrative_embedding IS NOT NULL;

CREATE INDEX idx_profiles_active_gender_age ON profiles (is_active, gender, age)
  WHERE is_active = TRUE;

CREATE INDEX idx_profiles_location ON profiles
  USING gist (ll_to_earth(location_lat, location_lng))
  WHERE location_lat IS NOT NULL AND location_lng IS NOT NULL;

-- Profiling conversation storage
CREATE TABLE profiling_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    messages JSONB NOT NULL DEFAULT '[]',
    extracted_traits JSONB,
    narrative TEXT,
    coverage JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_profiling_conv_profile ON profiling_conversations(profile_id);

-- Incremental matching support
ALTER TABLE matches ADD COLUMN stale BOOLEAN DEFAULT FALSE;
CREATE INDEX idx_matches_stale ON matches(stale) WHERE stale = TRUE;
```

**Verify**: `supabase db push`, then check extensions (`SELECT * FROM pg_available_extensions WHERE name IN ('vector','cube','earthdistance');`) and indexes (`\di`).

---

## Phase 1a: Adaptive Profiling Engine (core, no SMS yet)

Replace the fixed questionnaire with a Claude-driven conversation that adapts follow-ups based on user responses and pool context.

### Files to create

| File                                 | Purpose                                                            |
| ------------------------------------ | ------------------------------------------------------------------ |
| `src/kandal/profiling/__init__.py`   | Package init                                                       |
| `src/kandal/profiling/engine.py`     | Conversation engine — decides next question, tracks trait coverage |
| `src/kandal/profiling/prompts.py`    | System prompts, extraction schemas                                 |
| `src/kandal/profiling/extractor.py`  | Structured trait extraction from conversation via Claude           |
| `src/kandal/profiling/embeddings.py` | Narrative embedding via Voyage AI                                  |
| `src/kandal/profiling/pool_stats.py` | Compute pool-level stats for pool-aware probing                    |

### Files to modify

| File                           | Change                                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------------------ |
| `src/kandal/core/config.py`    | Add `anthropic_api_key`, `voyageai_api_key` settings                                             |
| `src/kandal/models/profile.py` | Add `narrative`, `narrative_embedding`, `profile_version`, `embedding_version` fields (optional) |
| `pyproject.toml`               | Add `anthropic>=0.40`, `voyageai>=0.3` dependencies                                              |

### Key interfaces

```python
# src/kandal/profiling/engine.py
@dataclass
class ProfilingState:
    profile_id: UUID
    messages: list[dict]           # [{role, content}]
    coverage: dict[str, float]     # trait -> confidence (0-1)
    questions_asked: int
    max_questions: int = 10

class ProfilingEngine:
    async def next_turn(self, state: ProfilingState, user_reply: str) -> ProfilingTurn:
        """Process user reply, return next question or completion."""
        # 1. Append user reply to messages
        # 2. Call Claude to assess coverage + generate next question
        # 3. If all traits >= 0.7 confidence or max_questions hit → extract + finalize
        ...

@dataclass
class ProfilingTurn:
    reply: str                              # next question or closing message
    is_complete: bool
    traits: InferredTraits | None = None    # same model from questionnaire/inference.py
    narrative: str | None = None
```

**Reuse**: `InferredTraits` from `kandal/questionnaire/inference.py:26` is the output contract. The adaptive profiler must produce the same model so downstream scoring is unchanged.

**Pool-aware probing**: `pool_stats.py` queries aggregate stats (trait distributions, common interests) for users matching this user's dealbreaker criteria. The profiler's system prompt includes: "The pool has many {dominant_trait} users. Ask questions that help distinguish this person on {low_coverage_dimension}."

**LLM strategy**: Two Claude calls per turn:

1. **Conversation call**: Generate next question (or signal completion). Uses `claude-haiku-4-5` for speed (~500ms).
2. **Extraction call** (final turn only): Extract `InferredTraits` + narrative from full conversation. Uses `claude-sonnet-4-6` with tool use for structured output.

### Testing

- Unit test with mocked Anthropic client: script a 6-turn conversation, verify `InferredTraits` output has all fields populated.
- Test coverage tracking: verify engine asks follow-ups when a dimension has low confidence.
- Test pool-aware probing: verify system prompt includes pool stats when provided.

---

## Phase 1b: SMS Integration

Wire the adaptive profiler into the existing SMS onboarding flow.

### Files to modify

| File                        | Change                                                                                                                                                                                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/kandal/sms/handler.py` | Replace `onboarding_q1`..`q10` states with single `adaptive_profiling` state. In this state, each inbound message goes to `ProfilingEngine.next_turn()`. On completion, transition to `collecting_name`. Fallback: if Claude API fails, fall back to old fixed questions. |

### Key change in handler state machine

```
Before: awaiting_code → q1 → q2 → ... → q10 → collecting_name → ... → complete
After:  awaiting_code → adaptive_profiling → collecting_name → ... → complete
```

The `_finalize()` function already writes `InferredTraits` to preferences — no change needed there. Just add: write narrative + embedding to profiles table.

### Testing

- Mock `ProfilingEngine`, verify SMS handler state transitions correctly.
- Test fallback: simulate Claude API failure, verify handler falls back to fixed questions.

---

## Phase 2a: Scalable Candidate Generation

Replace `itertools.combinations()` with DB-level candidate generation. This is the highest-impact change for scalability.

### Files to create

| File                                | Purpose                                                     |
| ----------------------------------- | ----------------------------------------------------------- |
| `src/kandal/matching/__init__.py`   | Package init                                                |
| `src/kandal/matching/candidates.py` | SQL-based candidate generation (dealbreakers + ANN ranking) |
| `src/kandal/matching/pipeline.py`   | New matching pipeline: candidates → score → verdict         |

### Files to modify

| File                          | Change                                                                      |
| ----------------------------- | --------------------------------------------------------------------------- |
| `src/kandal/scripts/match.py` | Replace `run_batch()` internals to call new pipeline. Keep the entry point. |

### Candidate generation SQL (core of `candidates.py`)

For each user, one query returns their top-k candidates with all dealbreakers checked in SQL:

```sql
SELECT c.id AS candidate_id,
       1 - (p.narrative_embedding <=> c.narrative_embedding) AS embedding_sim,
       earth_distance(ll_to_earth(p.location_lat, p.location_lng),
                      ll_to_earth(c.location_lat, c.location_lng)) / 1000.0 AS distance_km
FROM profiles p
JOIN preferences up ON up.profile_id = p.id
CROSS JOIN LATERAL (
    SELECT c2.id, c2.narrative_embedding, c2.location_lat, c2.location_lng
    FROM profiles c2
    JOIN preferences cp ON cp.profile_id = c2.id
    WHERE c2.id != p.id
      AND c2.is_active = TRUE
      AND (up.gender_preferences = '{}' OR c2.gender = ANY(up.gender_preferences))
      AND c2.age BETWEEN up.min_age AND up.max_age
      AND (cp.gender_preferences = '{}' OR p.gender = ANY(cp.gender_preferences))
      AND p.age BETWEEN cp.min_age AND cp.max_age
      AND up.relationship_types && cp.relationship_types
      AND (p.location_lat IS NULL OR c2.location_lat IS NULL
           OR earth_distance(ll_to_earth(p.location_lat, p.location_lng),
                             ll_to_earth(c2.location_lat, c2.location_lng))
              <= LEAST(up.max_distance_km, cp.max_distance_km) * 1000)
    ORDER BY p.narrative_embedding <=> c2.narrative_embedding
    LIMIT $2
) c
WHERE p.id = $1;
```

For users without embeddings: fall back to random ordering within dealbreaker-passing set.

### New pipeline flow

```python
# src/kandal/matching/pipeline.py
def match_user(profile_id: UUID, candidate_limit: int = 200) -> list[dict]:
    candidates = CandidateGenerator().get_candidates(profile_id, limit=candidate_limit)
    user_profile, user_prefs = load_profile_and_prefs(profile_id)
    matches = []
    for cand in candidates:
        cand_profile, cand_prefs = load_profile_and_prefs(cand.candidate_id)
        result = score_compatibility(user_profile, user_prefs, cand_profile, cand_prefs)
        verdict = compute_verdict(result, user_prefs.selectivity, cand_prefs.selectivity)
        if verdict == "match":
            matches.append(build_match_row(profile_id, cand.candidate_id, result, verdict))
    return matches

def run_pipeline(batch_size: int = 100) -> dict:
    user_ids = get_active_user_ids()
    all_matches = []
    for batch in chunked(user_ids, batch_size):
        for uid in batch:
            all_matches.extend(match_user(uid))
        upsert_matches(all_matches)  # batch upsert
        all_matches.clear()
    return stats
```

### Scaling math

| Users | Current (combinations) | New (200 candidates/user) | Speedup |
| ----- | ---------------------- | ------------------------- | ------- |
| 1k    | 500k pairs             | 200k scoring calls        | 2.5x    |
| 10k   | 50M pairs              | 2M scoring calls          | 25x     |
| 100k  | 5B pairs               | 20M scoring calls         | 250x    |

### Testing

- Seed 100 test profiles in local Supabase, verify candidate SQL returns correct results (all pass bidirectional dealbreakers).
- Regression test: run old and new pipelines on same dataset, verify same matches produced.
- Benchmark: seed 10k profiles, measure total pipeline time.

---

## Phase 2b: Narrative Similarity Scoring Dimension

Add semantic matching as the 10th scoring dimension.

### Files to modify

| File                           | Change                                                                                                                                                                                                                                                         |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `src/kandal/scoring/engine.py` | Add `narrative_similarity` dimension (weight 0.15). Rebalance existing weights proportionally to sum to 1.0. Add `_score_narrative_similarity()` that computes cosine similarity between `profile.narrative_embedding` vectors. Returns 0.5 if either is None. |
| `src/kandal/models/profile.py` | Ensure `narrative_embedding: list[float]                                                                                                                                                                                                                       | None` is on the model |

**Note**: Current scoring functions take `(prefs_a, prefs_b)`. The narrative embedding lives on `Profile`, not `Preferences`. The `score_compatibility` function already receives profiles — we just need to pass them to the new dimension function. Update `_SCORE_FNS` to allow functions that take profiles:

```python
# Dimension functions can take (prefs_a, prefs_b) OR (profile_a, prefs_a, profile_b, prefs_b)
def _score_narrative_similarity(profile_a: Profile, prefs_a: Preferences,
                                 profile_b: Profile, prefs_b: Preferences) -> float:
    if not profile_a.narrative_embedding or not profile_b.narrative_embedding:
        return 0.5
    return _cosine_similarity(profile_a.narrative_embedding, profile_b.narrative_embedding)
```

Unify the scoring function dispatch to pass all four args to every function (existing functions just ignore the profile args via `**kwargs` or we update their signatures).

### Testing

- Unit test: identical embeddings → 1.0, orthogonal → ~0.0, one missing → 0.5.
- Regression: existing test cases produce same Tier 1/2 scores (just scaled down).

---

## Phase 3: Incremental Matching

Only re-score users whose profiles changed.

### Files to modify/create

| File                                | Change                                                                                                               |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `src/kandal/matching/pipeline.py`   | Add `match_changed_users()` that queries users where `profile_version > embedding_version` or who have stale matches |
| `src/kandal/api/routes/profiles.py` | On profile/preferences update, increment `profile_version` and mark existing matches as `stale`                      |

### Testing

- Update one profile in a 100-user pool, verify only that user's matches are re-scored.

---

## Dependency Graph

```
Phase 0 (SQL migration)
├── Phase 1a (profiling engine)      ← can parallel with 2a
│   └── Phase 1b (SMS integration)
├── Phase 2a (candidate generation)  ← HIGHEST IMPACT
│   ├── Phase 2b (narrative scoring)
│   └── Phase 3 (incremental matching)
```

Phases 1a and 2a are independent and can be built in parallel.

---

## New Dependencies

| Package           | Purpose                                                   |
| ----------------- | --------------------------------------------------------- |
| `anthropic>=0.40` | Claude API for profiling conversations + trait extraction |
| `voyageai>=0.3`   | Embedding API (Voyage AI voyage-3-lite, 1024 dims)        |

No new infrastructure — pgvector and earthdistance are available in Supabase.

---

## Verification Plan

1. **Phase 0**: Run migration, verify extensions and indexes exist
2. **Phase 1a**: `pytest tests/test_profiling.py` — mock Claude, verify trait extraction produces valid `InferredTraits`
3. **Phase 1b**: `pytest tests/test_sms_handler.py` — verify adaptive profiling state transitions
4. **Phase 2a**: Seed 100 profiles locally, run `python -m kandal.scripts.match`, verify matches produced and all pass dealbreakers
5. **Phase 2b**: `pytest tests/test_scoring.py` — verify new dimension doesn't break existing scores
6. **Phase 3**: Update one profile, run incremental pipeline, verify only affected matches re-scored
7. **End-to-end**: Full onboarding via SMS → profiling → matching → verify match results include narrative similarity
