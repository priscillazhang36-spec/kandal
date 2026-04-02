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

## Current State

| Component | Status |
|-----------|--------|
| SMS onboarding | Live — text START to +12605973322 |
| Profile + trait creation | Working end-to-end |
| Scoring engine (9 dimensions) | Complete |
| Batch matching | Runs daily + on-demand via API |
| Vercel deployment | Live with auto-deploy |
| Match notifications | Not yet built |
| Second test user | Needed to test matching |

## Tech Stack

- **Language:** Python 3.12
- **API:** FastAPI (Vercel serverless)
- **Database:** Supabase (PostgreSQL)
- **SMS:** Twilio
- **Hosting:** Vercel
- **Testing:** pytest (85 tests)
