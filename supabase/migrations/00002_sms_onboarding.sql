-- Add phone to profiles, make basics nullable (filled in during onboarding)
ALTER TABLE profiles ADD COLUMN phone TEXT UNIQUE;
ALTER TABLE profiles ALTER COLUMN name DROP NOT NULL;
ALTER TABLE profiles ALTER COLUMN age DROP NOT NULL;
ALTER TABLE profiles ALTER COLUMN gender DROP NOT NULL;

-- Add Tier 2 trait columns to preferences
ALTER TABLE preferences ADD COLUMN attachment_style TEXT;
ALTER TABLE preferences ADD COLUMN love_language_giving TEXT[] DEFAULT '{}';
ALTER TABLE preferences ADD COLUMN love_language_receiving TEXT[] DEFAULT '{}';
ALTER TABLE preferences ADD COLUMN conflict_style TEXT;
ALTER TABLE preferences ADD COLUMN relationship_history TEXT;

-- Onboarding session state machine
CREATE TABLE onboarding_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL DEFAULT 'awaiting_code',
    verification_code TEXT,
    code_expires_at TIMESTAMPTZ,
    code_attempts INTEGER DEFAULT 0,
    profile_id UUID REFERENCES profiles(id),
    answers JSONB DEFAULT '[]',
    collected_basics JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_onboarding_phone ON onboarding_sessions(phone);
