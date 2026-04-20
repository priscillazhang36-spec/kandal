-- Restructure test_matches to store every pair (including dealbreaker-failed
-- ones) and tag each row with the model used for judging. Enables:
--   - troubleshooting why a pair didn't match (dealbreaker vs low LLM score)
--   - comparing verdicts across models (Opus vs Haiku) on the same pairs
--
-- DROP + CREATE is safe: test_matches has no production data.

DROP TABLE test_matches;

CREATE TABLE test_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_a_id UUID NOT NULL REFERENCES test_profiles(id) ON DELETE CASCADE,
    profile_b_id UUID NOT NULL REFERENCES test_profiles(id) ON DELETE CASCADE,
    model TEXT NOT NULL,                  -- e.g. 'claude-opus-4-7', 'claude-haiku-4-5'
    pass_dealbreaker BOOLEAN NOT NULL,
    score DOUBLE PRECISION,               -- NULL when pass_dealbreaker=false (no LLM call)
    is_matched BOOLEAN NOT NULL,          -- true iff score >= threshold
    llm_summary TEXT,
    llm_reasons JSONB DEFAULT '[]',
    llm_concerns JSONB DEFAULT '[]',
    judged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (profile_a_id, profile_b_id, model)
);

CREATE INDEX idx_test_matches_profile_a ON test_matches(profile_a_id);
CREATE INDEX idx_test_matches_profile_b ON test_matches(profile_b_id);
CREATE INDEX idx_test_matches_model ON test_matches(model);

NOTIFY pgrst, 'reload schema';
