-- Temporary landing table for guest profiles loaded from the Cinder
-- Google Sheet (tabs: "registered women" and "available men"). Union of
-- both tabs' columns; tab-specific fields are nullable. The `gender`
-- column distinguishes the two cohorts and is set by the loader.

CREATE TABLE cinder_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT now(),

    age INTEGER,
    first_name TEXT,
    last_name TEXT,
    gender TEXT NOT NULL,
    photo_url TEXT,
    relationship_intent TEXT,
    ethnicity TEXT,
    politics TEXT,
    religion TEXT,
    occupation TEXT,
    income_range TEXT,
    mbti TEXT,

    -- Big Five (men's tab only). REAL: values carry half-steps (e.g. 4.5).
    extroversion REAL,
    agreeableness REAL,
    conscientiousness REAL,
    neuroticism REAL,
    openness REAL,

    qualities TEXT,
    hobbies TEXT,
    attractiveness INTEGER,
    intelligence INTEGER,
    social_energy TEXT,
    height INTEGER,
    body_type TEXT,
    education_level TEXT,
    has_kids TEXT,
    wants_kids TEXT,
    activity_score INTEGER,
    alcohol_score INTEGER,
    smoking_score INTEGER,
    cannabis_score INTEGER,

    preferences_updated_at TIMESTAMPTZ,
    preferences TEXT,
    preference1 TEXT,
    preference2 TEXT,
    preference3 TEXT,
    preference_profile TEXT,

    -- Outreach tracking (men's tab only)
    may_invite TEXT,
    may_response TEXT,
    april_invite TEXT,
    april_response TEXT
);

NOTIFY pgrst, 'reload schema';
