-- Output of the cinder_match algorithm: per-woman ranked shortlists of men.
-- One row per (woman, man) judged pair; `rank` is the man's position in that
-- woman's shortlist (1 = best). FKs point at cinder_profiles (not profiles).
-- The LLM judge is the single scorer; `score` is its verdict.

CREATE TABLE cinder_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    woman_id UUID NOT NULL REFERENCES cinder_profiles(id) ON DELETE CASCADE,
    man_id   UUID NOT NULL REFERENCES cinder_profiles(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,                 -- 1 = top match for this woman
    score DOUBLE PRECISION,                -- LLM judge score, 0-1
    llm_summary TEXT,
    llm_scene TEXT,                        -- imagined first date (audit-friendly)
    llm_reasons JSONB DEFAULT '[]',
    llm_concerns JSONB DEFAULT '[]',
    passed_baseline BOOLEAN NOT NULL DEFAULT true,
    judged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (woman_id, man_id)
);

CREATE INDEX idx_cinder_matches_woman ON cinder_matches(woman_id);
CREATE INDEX idx_cinder_matches_rank  ON cinder_matches(woman_id, rank);

NOTIFY pgrst, 'reload schema';
