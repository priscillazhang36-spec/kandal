-- Profiles
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 18),
    gender TEXT NOT NULL,
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    city TEXT,
    bio TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Preferences / agent config
CREATE TABLE preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,

    -- Dealbreakers (Stage 1)
    min_age INTEGER NOT NULL DEFAULT 18,
    max_age INTEGER NOT NULL DEFAULT 99,
    max_distance_km INTEGER NOT NULL DEFAULT 50,
    gender_preferences TEXT[] NOT NULL DEFAULT '{}',
    relationship_types TEXT[] NOT NULL DEFAULT '{"long_term"}',

    -- Scoring dimensions (Stage 2)
    interests TEXT[] DEFAULT '{}',
    personality TEXT[] DEFAULT '{}',
    values TEXT[] DEFAULT '{}',
    communication_style TEXT DEFAULT 'balanced',
    lifestyle TEXT[] DEFAULT '{}',

    -- Selectivity (Stage 3)
    selectivity TEXT NOT NULL DEFAULT 'balanced'
);

-- Match results
CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_a_id UUID NOT NULL REFERENCES profiles(id),
    profile_b_id UUID NOT NULL REFERENCES profiles(id),
    score DOUBLE PRECISION NOT NULL,
    breakdown JSONB NOT NULL DEFAULT '{}',
    verdict TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (profile_a_id, profile_b_id)
);

CREATE INDEX idx_matches_profile_a ON matches(profile_a_id);
CREATE INDEX idx_matches_profile_b ON matches(profile_b_id);
CREATE INDEX idx_preferences_profile ON preferences(profile_id);
