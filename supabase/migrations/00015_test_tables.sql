-- Test tables for synthetic matching runs. Mirror the prod schema for the
-- columns the code actually reads (Profile + Preferences pydantic models),
-- skipping vector/embedding columns since the simplified 2-stage pipeline
-- no longer consumes them.

CREATE TABLE test_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    age INTEGER CHECK (age >= 18),
    gender TEXT,
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    city TEXT,
    bio TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    narrative TEXT,
    profile_version INTEGER NOT NULL DEFAULT 1,
    embedding_version INTEGER NOT NULL DEFAULT 0,
    last_significant_change TIMESTAMPTZ DEFAULT now(),
    birth_date DATE,
    birth_time_approx TEXT,
    birth_city TEXT,
    emotional_giving TEXT,
    emotional_needs TEXT,
    taste_fingerprint TEXT,
    current_obsession TEXT,
    two_hour_topic TEXT,
    contradiction_hook TEXT,
    past_attraction TEXT,
    favorite_places JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE test_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL UNIQUE REFERENCES test_profiles(id) ON DELETE CASCADE,
    min_age INTEGER NOT NULL DEFAULT 18,
    max_age INTEGER NOT NULL DEFAULT 99,
    max_distance_km INTEGER NOT NULL DEFAULT 50,
    gender_preferences TEXT[] NOT NULL DEFAULT '{}',
    relationship_types TEXT[] NOT NULL DEFAULT '{"long_term"}',
    interests TEXT[] DEFAULT '{}',
    personality TEXT[] DEFAULT '{}',
    partner_personality TEXT[] NOT NULL DEFAULT '{}',
    values TEXT[] DEFAULT '{}',
    partner_values TEXT[] NOT NULL DEFAULT '{}',
    communication_style TEXT DEFAULT 'balanced',
    lifestyle TEXT[] DEFAULT '{}',
    selectivity TEXT NOT NULL DEFAULT 'balanced',
    cultural_preferences TEXT[] DEFAULT '{}',
    dimension_weights JSONB,
    attachment_style TEXT,
    love_language_giving TEXT[] DEFAULT '{}',
    love_language_receiving TEXT[] DEFAULT '{}',
    conflict_style TEXT,
    relationship_history TEXT,
    humor_style TEXT,
    conversational_texture TEXT,
    energy_pace TEXT,
    ambition_shape TEXT
);

CREATE TABLE test_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_a_id UUID NOT NULL REFERENCES test_profiles(id) ON DELETE CASCADE,
    profile_b_id UUID NOT NULL REFERENCES test_profiles(id) ON DELETE CASCADE,
    score DOUBLE PRECISION NOT NULL,
    llm_summary TEXT,
    llm_reasons JSONB DEFAULT '[]',
    llm_concerns JSONB DEFAULT '[]',
    judged_at TIMESTAMPTZ,
    verdict TEXT NOT NULL DEFAULT 'match',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (profile_a_id, profile_b_id)
);

CREATE INDEX idx_test_preferences_profile ON test_preferences(profile_id);
CREATE INDEX idx_test_matches_profile_a ON test_matches(profile_a_id);
CREATE INDEX idx_test_matches_profile_b ON test_matches(profile_b_id);

NOTIFY pgrst, 'reload schema';
