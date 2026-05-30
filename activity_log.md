# Kandal — Activity Log

## Phase 1: MVP Scaffold
**What:** Built the full project from scratch based on CLAUDE.md spec.

- **Project structure** — Python 3.12, FastAPI, Supabase, src layout with `pyproject.toml`
- **Database schema** — `profiles`, `preferences`, `matches` tables (`supabase/migrations/00001_initial_schema.sql`)
- **Pydantic models** — Profile, Preferences, Match (`src/kandal/models/`)
- **API layer** — CRUD routes for profiles, matches, preferences (`src/kandal/api/`)
- **Scoring engine** — 5 Tier 1 dimensions using Jaccard similarity: interest overlap, personality match, values alignment, lifestyle signals, communication style (`src/kandal/scoring/engine.py`)
- **Dealbreaker filtering** — Bidirectional age, gender, distance (haversine), relationship type checks (`src/kandal/scoring/dealbreakers.py`)
- **Verdict logic** — Selectivity thresholds (picky/balanced/open) applied per-user (`src/kandal/scoring/verdict.py`)
- **Batch matching script** — 3-stage pipeline: dealbreakers → scoring → verdict (`src/kandal/scripts/match.py`)
- **Test suite** — 45 tests covering scoring, dealbreakers, verdicts, API

## Phase 2: Tier 2 Personality Dimensions
**What:** Added deeper compatibility scoring based on relationship psychology.

- **4 new scoring dimensions** — attachment style, love language fit, conflict style, relationship history (`src/kandal/scoring/engine.py`)
- **Compatibility matrices** — Attachment (secure+secure=1.0, anxious+avoidant=0.0) and conflict style matrices based on relationship science
- **Love language scoring** — Asymmetric: A's giving vs B's receiving, averaged both directions, ranked lists
- **Scenario-based questionnaire** — 10 questions that infer traits from behavior, not self-reporting (`src/kandal/questionnaire/questions.py`)
- **Trait inference engine** — Accumulates signal counts per trait, uses argmax with tie-breaking priority (`src/kandal/questionnaire/inference.py`)
- **Interactive demo** — CLI tool to answer questions and see match breakdown against 6 NPC profiles (`demo.py`)
- **Test suite expanded** — 65 tests total (+10 questionnaire, +14 Tier 2 scoring)

## Phase 3: SMS Onboarding via Twilio
**What:** Poke-style onboarding where users text a phone number and complete the questionnaire over SMS.

- **Twilio integration** — Send/receive SMS via Twilio REST API (`src/kandal/sms/service.py`)
- **State machine** — Tracks each user through: START → 10 questions → name → age → gender → city → complete (`src/kandal/sms/handler.py`)
- **Onboarding sessions table** — Persistent state in Supabase, survives server restarts (`supabase/migrations/00002_sms_onboarding.sql`)
- **Conversational messages** — Friendly tone with random transition phrases between questions (`src/kandal/sms/messages.py`)
- **Webhook endpoint** — `POST /sms/webhook` receives Twilio POSTs, routes through state machine (`src/kandal/api/routes/auth.py`)
- **Profile creation** — On START: creates profile row. On completion: updates with basics, upserts inferred traits to preferences.
- **Answer parsing** — Accepts A/B/C/D (case-insensitive) or 1/2/3/4. Invalid input = retry with friendly nudge.
- **DB migration** — Phone column on profiles, nullable basics, Tier 2 columns on preferences, onboarding_sessions table
- **Test suite expanded** — 85 tests total (+20 SMS onboarding)

## Phase 4: Deployment
**What:** Deployed the full application to Vercel with production infrastructure.

- **Vercel serverless deployment** — FastAPI running as a serverless function (`api/index.py`, `vercel.json`)
- **Environment variables** — Supabase (service_role key) and Twilio credentials configured on Vercel
- **GitHub auto-deploy** — Connected repo so every push to `main` triggers a deployment
- **Matching API endpoint** — `POST /matches/run` triggers the batch matching pipeline on demand
- **Daily cron job** — Vercel cron runs matching once per day at midnight UTC
- **Production URL** — `https://kandal.vercel.app`
- **Twilio webhook** — Points to `https://kandal.vercel.app/sms/webhook`

## Phase 5: Landing Page
**What:** Built a public-facing landing page at kandal.app for user acquisition.

- **Poke.com-inspired design** — Dark theme, JetBrains Mono typography, amber accent, full-viewport sections (`public/index.html`)
- **Sections** — Hero ("Dating, decoded."), How It Works (3 steps), Value Props (anti-dating app), Phone signup CTA
- **Phone registration form** — Collects phone number, calls `POST /auth/start`, triggers SMS onboarding flow
- **Vercel routing** — Static landing page served at `/`, all API routes unchanged (`vercel.json`)
- **Mobile-first responsive** — Stacked layout on mobile, 3-column grid on desktop
- **Domain** — kandal.app purchased (Squarespace)

## Phase 6: Profiling Overhaul + Bazi Integration
**What:** Overhauled the profiling conversation to position the agent as the user's "dating alter ego," added Bazi compatibility, and improved conversation quality.

- **Digital alter ego positioning** — Rewrote all profiling prompts to frame the agent as the user's dating alter ego, not a matchmaker (`src/kandal/profiling/prompts.py`)
- **Natural conversation style** — System prompt now instructs varied message lengths (1-4 sentences), best friend energy, casual tone
- **Partner preference questions** — Conversation now surfaces gender preference and cultural/racial preferences naturally
- **Bazi (Four Pillars) module** — Pure-function module computing Four Pillars from birth date/time, scoring element compatibility via generating/controlling cycles, Six Harmonies, Three Harmonies, and Six Clashes (`src/kandal/scoring/bazi.py`)
- **Birth info collection** — Conversation asks for birthday, approximate birth time (3hr window), and birthplace for Bazi matching
- **Bazi scoring dimension** — Added `bazi_compatibility` as a new Tier 2 scoring dimension at 0.09 weight, rebalanced all weights to sum to 1.0 (`src/kandal/scoring/engine.py`)
- **Profile summary confirmation** — After profiling, generates a summary for the user to confirm before locking in. Handles corrections via re-extraction.
- **Extended extraction** — Extracts gender_preference, cultural_preferences, birth_date, birth_time_approx, birth_city from conversation (`src/kandal/profiling/extractor.py`)
- **Extended models** — Added birth fields to Profile, cultural_preferences to Preferences, optional fields to InferredTraits
- **DB migration** — `00004_bazi_and_preferences.sql`: birth_date/time/city on profiles, cultural_preferences on preferences
- **SMS handler updates** — Supports `awaiting_confirmation` state, persists birth info and new preference fields

## Phase 7: Scoring Intelligence + Error Monitoring
**What:** Made matching smarter with semantic similarity and cross-comparison, added Sentry error monitoring, legal pages for Twilio TFV, and cost optimization.

- **Sentry error monitoring** — Auto-captures unhandled exceptions via FastAPI integration, `logger.error()` forwarding, hardened `critical_alert()` for wake-up failures (`src/kandal/core/alerts.py`)
- **Semantic similarity scoring** — Replaced naive Jaccard with Voyage AI embeddings + cosine similarity for personality and values matching (`src/kandal/scoring/engine.py`)
- **Cross-comparison matching** — Personality/values now scored as A's traits vs B's partner_wants (complementarity), not same-to-same overlap. Added `partner_personality`, `partner_values` fields end-to-end.
- **Weight redistribution** — Dimensions with no data get weight 0, remaining weights scale proportionally instead of defaulting to 0.5
- **Tier 1 tag extraction** — Interests, personality, values, lifestyle now extracted from profiling conversations and saved to preferences
- **Coverage tracking** — Added `interests_and_lifestyle` dimension so profiling asks about hobbies
- **Conversation flow overhaul** — Reordered phases (vibes first, basics last), removed structured response pattern, more natural tone
- **Emotional fit scoring** — Added Tier 0 `emotional_fit` dimension (0.25 weight) comparing giving/needs narrative embeddings
- **Legal pages** — Privacy policy and terms of service for Twilio toll-free verification (`src/kandal/api/legal.py`)
- **Landing page consent** — Added opt-in checkbox with legal links for TFV compliance
- **Cost optimization** — Switched `extract_traits` from Claude Sonnet to Haiku (~15x cost reduction)
- **DB migration** — `00006_partner_preferences.sql`: partner_personality, partner_values columns on preferences

## Phase 8: Conversation UX improvements (user feedback)
**What:** Improved conversation experience based on test user feedback.

- **Expectation setting** — Opening message now tells users: ~12-15 questions, 10-15 min, a sentence or two per answer is fine (`src/kandal/profiling/engine.py`)
- **Softer follow-ups** — Reworked vague-answer handling: offer scenarios/this-or-that instead of calling out dodged questions; let go after one gentle reframe and circle back later from a different angle (`src/kandal/profiling/prompts.py`)
- **Tone adjustment** — Replaced "cop-out answer" challenge style with gentler nudges; fold missed sub-questions into next turn naturally instead of "you never answered X"

## Phase 9: Spark-first Onboarding
**What:** Reframed onboarding around first-date "spark" signals (taste, humor, aliveness, conversational texture) instead of interrogating long-term compatibility in freeform. Long-term traits now come from a tight MCQ loop; freeform captures the texture a human actually flirts with.

- **Spark signal schema** — New columns on profiles + preferences: `taste_fingerprint`, `current_obsession`, `two_hour_topic`, `contradiction_hook`, `past_attraction`, `favorite_places` (JSONB list) (`supabase/migrations/00013_spark_signals.sql`)
- **Trait dimensions rewritten** — Freeform agent now pursues 5 spark-leaning dimensions: `spark_aliveness`, `spark_taste`, `spark_attraction`, `emotional_dynamics`, `partner_vibe` (`src/kandal/profiling/prompts.py`)
- **Soul file refocused** — `soul.md` recentered on first-date predictors (taste, humor, aliveness) vs long-term stickiness; explicit persona + hallucination guards retained
- **Stop milking small talk** — Phase-1 `phase_hint` now has an explicit "don't milk small talk" rule with the cat-ladder failure mode called out verbatim (one clarifying beat per topic, then pivot)
- **Opener rewritten** — `OPENING_MESSAGE` pulls for current_obsession on turn 1 instead of generic "what made you smile this week"
- **Spark scenario MCQs** — 4 new MCQs capturing humor_style, conversational_texture, energy_pace, ambition_shape (`src/kandal/profiling/spark_mcqs.py`)
- **Long-term MCQs trimmed** — Cut from 10 to 4 focused scenario questions for attachment, love language, conflict, relationship_history (`src/kandal/questionnaire/questions.py`)
- **Conversation flow chain** — Deterministic loop: freeform → summary confirm → spark MCQs (4) → long-term MCQs (4) → basics MCQs → finalize (`src/kandal/profiling/engine.py`)
- **Resumable state** — Added `spark_index`, `longterm_index`, `longterm_answers` JSONB columns so SMS conversations survive gaps (`supabase/migrations/00014_spark_longterm_indices.sql`, `src/kandal/sms/handler.py`)
- **Extractor split** — Freeform no longer infers attachment/LL/conflict/history (those now come from MCQs, marked `low_conf` until overwritten). Spark fields extracted as validated text + favorite_places as list of dicts (`src/kandal/profiling/extractor.py`)
- **Ranking removed** — Dimension-weight ranking question gone; Stage B LLM judge will read raw signals directly. `dimension_weights` retained nullable on models for backcompat
- **Tests** — 74 passing; questionnaire tests updated for the 4-question set

## Phase 10: Matching Pipeline Simplification
**What:** Collapsed the matching pipeline from 3 stages to 2 after realizing Stage 2 (embedding-based coarse ranking) was effectively dead code — the LLM judge was told to ignore its output, and for pools under 25 users the top-K cutoff was bypassed anyway.

- **Stage 2 removed** — Deleted `scoring/engine.py` (DIMENSION_WEIGHTS, score_compatibility, all tier-1/tier-2 scorers, Voyage embedding wrappers, cosine similarity helpers) and `scoring/verdict.py` (compute_verdict, selectivity thresholds)
- **Pipeline is now** — dealbreaker filter → LLM judge on every passing pair → write matches above `LLM_MATCH_THRESHOLD = 0.7` (`src/kandal/scripts/match.py`)
- **LLM judge simplified** — Dropped `coarse_score` parameter and the "for context only, don't anchor" line from the prompt (`src/kandal/scoring/llm_judge.py`)
- **Match model/schema** — Made `breakdown` and `verdict` optional with defaults, since neither is populated anymore (`src/kandal/models/match.py`, `src/kandal/schemas/match.py`)
- **Tests pruned** — Deleted `test_scoring.py`, `test_tier2_scoring.py`, `test_verdict.py` (all covered ripped code). 47 tests still passing.
- **Not yet cleaned up (follow-ups)** — `scoring/bazi.py` no longer wired into matching; `profiling/embeddings.py` still populates `narrative_embedding` / `emotional_giving_embedding` / `emotional_needs_embedding` on profiles but nothing reads them; `matches.coarse_score` / `llm_score` / `breakdown` columns still on the DB (writes stopped, not dropped); `demo.py` references removed symbols and is broken; `.claude/docs/matching_algorithm_spec.md` describes the old 3-stage pipeline.

## Phase 11: Synthetic Matching Test Harness
**What:** Added a reproducible end-to-end test framework for the 2-stage matching pipeline that runs against isolated `test_*` tables and lets Claude in-session act as the judge (no Anthropic API calls).

- **Test schema** — `test_profiles` / `test_preferences` mirror prod columns (`supabase/migrations/00015_test_tables.sql`). `test_matches` restructured to store *every* pair (including dealbreaker-failed) tagged by judging model, so the same pool can be re-judged across Opus / Haiku / prompt variants and compared (`00016_test_matches_all_pairs.sql`)
- **Synthetic profiles** — `src/kandal/scripts/synthetic_profiles.py` provides a hand-crafted archetype pool with full narratives, spark fields, and preferences
- **Two-phase driver** — `src/kandal/scripts/synthetic_test.py` splits into `gather` (clear tables, insert profiles, compute pair-level dealbreakers + judge cards) and `load` (read a verdicts JSON file and upsert rows tagged with `--model`). Claude reads the gather file between phases and writes the verdicts file directly
- **Judge model parameterised** — `judge_pair()` now accepts a `model` kwarg defaulting to Haiku 4.5, so the same function can be used for prompt/model experiments
- **Docs** — Full reproducible procedure in `docs/testing_matching.md` with pointer from `CLAUDE.md`
- **First run** — Both Opus 4.7 and Haiku 4.5 judged the same 60 dealbreaker-passing pairs. Full agreement on top matches (Deshawn+Nora at 0.90/0.89); the 6 disagreements clustered at the 0.68–0.74 threshold boundary with Haiku scoring consistently more conservative

## Phase 12: Spark-first Judge Prompt Iteration (v2 → v3)

**What:** Reworked the LLM judge prompt twice in one session after the Phase 11 baseline put register-mismatched pairs at the top of the list. Canary case: Deshawn+Nora scored 0.85+ across both models despite an obvious aesthete-craft (Ando, tasting board) vs grounded-utilitarian (hospital coffee, denim, burger) cultural-tribe mismatch — abstract trait similarity was masking a real first-date spark gap.

- **v2 — payload reorder + fenced narrative** — Rewrote `_format_person` in `src/kandal/scoring/llm_judge.py` so spark signals (`current_obsession`, `two_hour_topic`, `taste_fingerprint`, `contradiction_hook`, `past_attraction`, `favorite_places`, MCQ texture fields) lead the payload and narrative + `emotional_giving` / `emotional_needs` are fenced as incompatibility-check-only inputs. System prompt updated to forbid upgrading scores from warm narrative.
- **v3 — scene-imagination prompt** — v2 still anchored on life-stage compatibility because the prompt was structurally a checklist (list of dimensions + 80/20 weight math). v3 strips the criteria entirely and forces the judge to **imagine the first 20 minutes of the date as a written scene**, then score from the scene. Removed the bulleted dimension list, removed weight math, removed "INCOMPATIBILITY CHECK ONLY" header. Kept score distribution guidance and the deal-killer-only role for narrative.
- **`scene` field added** — `LLMVerdict` dataclass gains `scene: str`; JSON output requires a 150-200 word scene as first field; `judge_pair()` parses + populates it. `max_tokens` bumped 600 → 1000 to accommodate the scene.
- **DB schema** — `experiment_run` column added to `test_matches` so v1 / v2 / v3 verdicts can coexist tagged by prompt variant; unique constraint extended to include it (`supabase/migrations/00017_test_matches_experiment_run.sql`). `synthetic_test.py load` now takes `--experiment-run`.
- **Validation against the 60-pair pool** — Re-judged via Opus 4.7 and Haiku 4.5 against the same `spark_first_v1` / `v2` profile pool. Pass criteria from the plan:
  - **Deshawn+Nora dropped to 0.50** (Haiku v3) — register mismatch now detected
  - **Genuine-spark pairs held**: Rafe+Nora 0.86, Elena+Leo 0.85, Maya+Leo + Ben+Maya + Ben+Elena 0.80, Ben+Mia 0.78
  - **Matched count (≥0.7)**: 11 in Haiku v3 (vs 18 in v1, 14 in v2) — within the 8-14 target band
  - **Scenes are concrete** — name actual artifacts/places/topics from each profile (Saunders paperback, McNally Jackson, Fort Tryon walk, hospital triage), not generic
- **Cost-quality tradeoff observed** — Haiku v3 averages ~14% lower scores than Opus v3 with tighter scene prose, but holds the prompt structure: the high-spark and register-mismatch verdicts agree within 0.02-0.05 across models. Production default remains Haiku 4.5.

## Phase 13: Onboarding v4 — Moment Elicitation, Visual Prefs, Dealbreaker Wiring

**What:** Rewrote the onboarding conversation to elicit grounded recent moments instead of abstract spark questions, captured verbatim user voice for the judge to read, added a visual-preference dimension, and wired the lifestyle basics into dealbreaker filtering with paired tolerance fields.

- **Conversation rewrite (v4)** — `ESSENTIAL_DIMENSIONS` in `src/kandal/profiling/engine.py` swapped from `emotional_dynamics` / `partner_vibe` / `spark_aliveness` to `lived_places` / `recent_rabbit_hole` / `recent_giving`. Opening message rewritten to start with a low-stakes "spot you've been in the last week or two" prompt instead of asking what they're "into right now"
- **Spark voice JSONB (v4.0)** — New `profiles.spark_voice` column (`supabase/migrations/00018_profile_spark_voice.sql`, mirrored on `test_profiles`) stores verbatim user-voice slices alongside the paraphrased structured fields: `taste_fingerprint_quote`, `current_obsession_quote`, `humor_example_quote`, `giving_quote`, `pull_quote`. Surfaces register/voice tells the LLM judge would otherwise lose to paraphrase
- **Visual preference (v4.1)** — `preferences.visual_type` (classic / artsy / athletic / no_strong_type) + `preferences.visual_preference` freeform (`00019_preferences_visual.sql`). Captured via spark MCQ + extractor, fed to the judge as a soft factor. Future phase will tie `visual_type` to photo-based pre-filtering
- **Dealbreaker wiring (v4.2)** — `preferences.partner_wants_kids` + `preferences.partner_substances_max` paired tolerance columns capture what the user accepts *from a partner* (not just their own state). `src/kandal/scoring/dealbreakers.py` extended to filter on these; `src/kandal/profiling/basics.py` collects them in the basics MCQ loop (`00020_dealbreaker_wiring.sql`)
- **test_preferences parity** — Migration 00020 mirrors the lifestyle-basics columns from prod (added in 00010) onto `test_preferences`, plus the new paired tolerance fields, so the `synthetic_test` harness can exercise dealbreakers end-to-end. `Preferences` Pydantic model gains the load-side fields for parity
- **Dropped fields** — Removed unused `partner_values` and `dimension_weights` from `Preferences`; `rescue.py` no longer references the dropped `partner_values` / `lifestyle` Traits paths
- **New test coverage** — `tests/test_dealbreakers.py` (20 cases) covers the v4.2 paired-tolerance filter behavior; `tests/conftest.py` extended with fixtures for the new fields
- **Terminal driver** — `src/kandal/scripts/onboard_test.py` runs the full v4 onboarding conversation in the terminal (freeform → confirm → spark MCQs → long-term MCQs → basics MCQs → finalize), writes to `test_profiles` / `test_preferences` by default, and prints the extracted traits + `spark_voice` JSONB at the end for inspection
- **Test count** — 60 tests passing (was 47 in Phase 10; tests/test_dealbreakers.py adds 20, partial offset from older deletions)
- **Deployment** — Single commit `7032bbe` pushed to `main`; migrations 00018–00020 applied to Supabase prior to push; Vercel auto-deployed from the push

## Phase 14: Ideal-Type Discovery Mode

**What:** Added a second onboarding flow `ideal_type_discovery` alongside the existing `full_discovery`. Designed for users who don't know what they want — uses revealed preference (past-pull excavation + LLM-generated forced-choice vignettes) instead of stated preference. <10-min target. Standalone alternative — does NOT make the user matchable; writes a separate ideal-type artifact only. `ideal_type_discovery` is now the default mode; `full_discovery` is opt-in.

- **5-stage flow** — Stage 0: ~9 partner-facing dealbreaker MCQs (gender, age range, ethnicity, religion, smoking/drinking/cannabis tolerance, kids, intent). Stage 1: past-pull excavation (recent + earlier contrasting attraction). Stage 2: the "ick" beat. Stage 3: LLM-generated vignette forced-choice (2-3 contrast pairs tuned to past pulls + respecting dealbreakers). Stage 4: one-shot pattern readback + yes/correction. Soft cap 6 freeform turns, hard cap 14.
- **Schema** — `supabase/migrations/00021_onboarding_mode.sql` adds `onboarding_sessions.mode` (default `ideal_type_discovery`); `00022_ideal_types.sql` creates the `ideal_types` table with structured dealbreaker columns, raw past_pulls/icks/vignettes/vignette_choices JSONB, and the synthesized artifact (pull_pattern + pull_pattern_quote + partner_traits)
- **New engine** — `src/kandal/profiling/ideal_type_engine.py` — separate `IdealTypeEngine` class (not a parametrized ProfilingEngine — too divergent in shape). `IdealTypeState` carries stage + dealbreaker_index + vignettes + pending_artifact
- **Vignette generator** — `src/kandal/profiling/ideal_type_vignettes.py` — single LLM call (`claude-sonnet-4-6`) takes past_pulls + icks + dealbreakers and returns 2-3 contrast pairs with named specifics. Hard guardrail: must respect demographic dealbreakers (gender, age, religion, substances, kids); both vignettes must be plausible — the choice should feel hard
- **Extractor + readback** — `src/kandal/profiling/ideal_type_extractor.py` synthesizes the artifact (paraphrased + verbatim quotes for every past pull and tipped reason). `ideal_type_prompts.py` includes phase-gated conversation prompt, lightweight binary coverage check, extraction prompt, and one-shot readback prompt
- **Dealbreaker MCQs** — `src/kandal/profiling/ideal_type_dealbreakers.py` — 9 partner-facing questions reusing the `_letter` parser pattern from `basics.py`. Skip-if-known for resumability
- **Route wiring** — `src/kandal/api/routes/chat.py:ChatStartRequest.mode` defaults to `ideal_type_discovery`; `chat_start` branches by mode and inserts to the right table. `_handle_ideal_type` helper loads state from the `ideal_types` row, drives one turn, persists messages + stage + sub_state, and on completion sets session `state="ideal_type_complete"`. SMS path (`auth.py`) explicitly sets `mode="full_discovery"` on session upsert since SMS doesn't have a mode picker
- **Models** — `IdealType`, `PastPull`, `VignetteChoice`, `VignettePair` Pydantic models in `src/kandal/models/ideal_type.py`. `OnboardingSession.mode` added
- **Tests** — `tests/test_ideal_type_engine.py` covers 10 state transitions with mocked Anthropic client (dealbreaker loop, freeform advancement, hard cap exit, coverage-check exit, vignette loop, readback yes/correction). Suite now 70 tests, all passing
- **CLI driver** — `test_ideal_type_live.py` walks the full flow against real Claude + Supabase and reports elapsed time

## Phase 15: Skip Stage 0 Dealbreakers (temporary)

**What:** Temporarily bypass the Stage 0 dealbreaker MCQs in `ideal_type_discovery` mode and reshape the opening so users land directly in the celebrity forced-choice with proper context.

- **Skip flag** — `SKIP_DEALBREAKERS = True` in `ideal_type_engine.py`. When set, `IdealTypeEngine.start()` jumps straight to `_start_celebrity_picks` with empty `dealbreaker_answers`. Flip to `False` to restore the full 10-question MCQ loop.
- **Reworded opening** — replaces the old `OPENING_MESSAGE` (which advertised "~7 quick picks") with a two-part roadmap: warm intro → "Two parts: first a few quick visual picks, then we'll talk through a past relationship that mattered. About 15 minutes total."
- **Celebrity intro de-anchored** — changed "Now a quick visual read" → "Quick visual read first" so the celebrity stage reads naturally whether it's the first thing the user sees (skip path) or follows dealbreakers (when flag is flipped back).
- **Downstream caveats (not patched)** — celebrity + vignette generators get empty `dealbreaker_answers`, so pairs are unfiltered (mixed-gender / no religion/substance/kids filters). Matching pipeline's Stage 1 dealbreaker filter has no constraints for users onboarded this way. `tests/test_ideal_type_engine.py` will fail at `start()` until updated.

## Phase 16: Animated Typing Indicator

**What:** Upgrade the web chat's typing indicator so long LLM calls (especially the freeform→vignette transition, which fires two back-to-back model calls) feel deliberate instead of frozen.

- **Animated dots** — `src/kandal/api/landing.py` now renders 3 cream-colored dots (7px, 75% opacity) inside the typing bubble, pulsing with a staggered keyframe animation (`@keyframes typing-pulse`, 1.3s loop, 180ms stagger, 3px bob). Bubble background bumped from `rgba(245,234,214,0.05)` → `0.08` for visibility against the `#0f0c15` background.
- **After-5s escalation** — `showTyping()` schedules a timer that swaps the dots for "still thinking — putting something together for you..." with a 0.45s fade-in (`@keyframes typing-text-in`). Keeps the italic + soft cream tone so it reads as a system whisper.
- **Cleanup** — `removeTyping()` clears the pending escalation timer so fast replies never trigger the swap.

## Current State

| Component | Status |
|-----------|--------|
| SMS onboarding | Live — text START to +12605973322 |
| Profile + trait creation | Working end-to-end |
| Scoring engine (11 dimensions) | Complete — semantic similarity, cross-comparison, Bazi |
| Bazi (Four Pillars) matching | Complete — pure function, graceful degradation |
| Profiling conversation | Two modes — `ideal_type_discovery` (default, partner-clarity, <10min) and `full_discovery` (opt-in, full profile, ~20min) |
| Batch matching | Runs daily + on-demand via API |
| Vercel deployment | Live with auto-deploy |
| Landing page | Live at kandal.app |
| Match notifications | Not yet built |
| Error monitoring | Sentry + hardened SMS alerts |
| Second test user | Needed to test matching |

## Tech Stack

- **Language:** Python 3.12
- **API:** FastAPI (Vercel serverless)
- **Database:** Supabase (PostgreSQL)
- **SMS:** Twilio
- **Hosting:** Vercel
- **Testing:** pytest (70 tests)
