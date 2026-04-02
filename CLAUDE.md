# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kandal is an agent-mediated dating matchmaking system. Instead of swiping, users configure preferences and an AI "agent" negotiates compatibility with other agents on their behalf via a blind protocol. Only mutual matches are surfaced.

**Current scope (MVP):** Prove the matching/scoring logic works. No real-time agents yet — the "agent" is a deterministic scoring function run as a batch script.

## Tech Stack

- **Language:** Python 3.12+
- **API:** FastAPI
- **Database:** Supabase (PostgreSQL) via `supabase-py`
- **Schema management:** SQL migration files in `supabase/migrations/`, applied via Supabase CLI (`supabase db push`) or dashboard
- **Testing:** pytest
- **Package management:** pip with pyproject.toml

## Project Structure

```
kandal/
├── src/kandal/
│   ├── api/              # FastAPI routes (profiles, matches)
│   ├── core/             # Config, Supabase client setup
│   ├── models/           # Pydantic models (DB row shapes)
│   ├── schemas/          # Pydantic request/response schemas
│   ├── scoring/          # Compatibility scoring logic
│   └── scripts/          # Batch matching entry point
├── supabase/migrations/  # SQL migration files
├── tests/
└── pyproject.toml
```

## Common Commands

```bash
# Install dependencies
pip install -e ".[dev]"

# Run API server
uvicorn kandal.api.main:app --reload

# Run batch matching
python -m kandal.scripts.match

# Run tests
pytest

# Run a single test file
pytest tests/test_scoring.py

# Run a single test
pytest tests/test_scoring.py::test_dealbreaker_filter -v
```

## Architecture

### Matching Pipeline (batch)

The matching script (`kandal/scripts/match.py`) runs the three-stage negotiation as a batch process:

1. **Stage 1 — Dealbreaker filtering:** Query active users, filter pairs by hard constraints (age range, distance, relationship type, gender preferences). Pure set intersection — no scoring yet.
2. **Stage 2 — Compatibility scoring:** For pairs that pass Stage 1, compute a weighted compatibility score across: interest overlap, personality match, values alignment, communication style, lifestyle signals.
3. **Stage 3 — Threshold verdict:** Pairs scoring above a configurable threshold become matches. Both users must independently exceed their own selectivity threshold (Picky/Balanced/Open maps to score cutoffs).

Matches are written to Supabase as `matches` rows with a compatibility summary.

### API Layer

Thin FastAPI layer for CRUD:
- User profiles and preferences
- Agent configuration (dealbreakers, weighted preferences, selectivity)
- Match results with compatibility summaries

### Scoring Design

Scoring lives in `kandal/scoring/` and is intentionally decoupled from the API and DB. The core function signature is:

```python
def score_compatibility(user_a: UserProfile, user_b: UserProfile) -> ScoringResult
```

This takes two complete profiles and returns a score + breakdown. It should remain a pure function with no DB or API calls — easy to test and iterate on.

## Environment Variables

```
SUPABASE_URL=         # Supabase project URL
SUPABASE_KEY=         # Supabase service role key (for backend use)
```

## Key Design Decisions

- **Supabase as DB layer:** Using `supabase-py` client, not SQLAlchemy. Schema managed via SQL migrations or Supabase dashboard.
- **No real-time agents yet:** The "agent" is a scoring function. Will evolve into an actual agent (with negotiation protocol, external agent support) once scoring is validated.
- **Batch over real-time:** Matching runs as a script, not a background worker. Can become a cron job or periodic task later.
- **Scoring is a pure function:** No side effects, no DB calls. Takes two profiles, returns a score. This is the core IP — keep it testable and iteratable.

## Activity Log

After every commit, update `activity_log.md` at the project root to reflect what was built or changed. Keep entries concise and organized by phase. This is the living record of project progress.
