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

## Current State

| Component | Status |
|-----------|--------|
| SMS onboarding | Live — text START to +12605973322 |
| Profile + trait creation | Working end-to-end |
| Scoring engine (11 dimensions) | Complete — semantic similarity, cross-comparison, Bazi |
| Bazi (Four Pillars) matching | Complete — pure function, graceful degradation |
| Profiling conversation | Overhauled — alter ego positioning, summary confirmation |
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
- **Testing:** pytest (85 tests)
