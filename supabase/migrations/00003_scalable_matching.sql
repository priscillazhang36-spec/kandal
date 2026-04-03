-- Phase 0: Database foundation for scalable matching + adaptive profiling
-- Adds pgvector, earthdistance, narrative embeddings, profiling conversations,
-- and indexes for efficient candidate generation.

-- Extensions (available on Supabase Free/Pro)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS cube;
CREATE EXTENSION IF NOT EXISTS earthdistance;

-- Profile extensions for narrative embeddings and versioning
ALTER TABLE profiles ADD COLUMN narrative TEXT;
ALTER TABLE profiles ADD COLUMN narrative_embedding vector(1024);
ALTER TABLE profiles ADD COLUMN profile_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE profiles ADD COLUMN embedding_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE profiles ADD COLUMN last_significant_change TIMESTAMPTZ DEFAULT now();

-- ANN index for embedding similarity (IVFFlat, good up to ~1M rows)
CREATE INDEX idx_profiles_embedding ON profiles
  USING ivfflat (narrative_embedding vector_cosine_ops)
  WITH (lists = 100)
  WHERE narrative_embedding IS NOT NULL;

-- Composite index for dealbreaker pre-filtering
CREATE INDEX idx_profiles_active_gender_age ON profiles (is_active, gender, age)
  WHERE is_active = TRUE;

-- Spatial index for bounding-box distance filtering
CREATE INDEX idx_profiles_location ON profiles
  USING gist (ll_to_earth(location_lat, location_lng))
  WHERE location_lat IS NOT NULL AND location_lng IS NOT NULL;

-- Profiling conversation storage (adaptive profiling sessions)
CREATE TABLE profiling_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    messages JSONB NOT NULL DEFAULT '[]',
    extracted_traits JSONB,
    narrative TEXT,
    coverage JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'in_progress',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_profiling_conv_profile ON profiling_conversations(profile_id);

-- Incremental matching support
ALTER TABLE matches ADD COLUMN stale BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX idx_matches_stale ON matches(stale) WHERE stale = TRUE;
