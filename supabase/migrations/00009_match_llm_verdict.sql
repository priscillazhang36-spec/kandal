-- LLM-judged compatibility verdict on matches. Three-stage pipeline:
-- (1) hard filters, (2) coarse ranker = existing weighted score, (3) LLM judge
-- on the top-K finalists per user. The LLM verdict is what users actually see.

ALTER TABLE matches ADD COLUMN coarse_score DOUBLE PRECISION;
ALTER TABLE matches ADD COLUMN llm_score DOUBLE PRECISION;
ALTER TABLE matches ADD COLUMN llm_summary TEXT;
ALTER TABLE matches ADD COLUMN llm_reasons JSONB DEFAULT '[]';
ALTER TABLE matches ADD COLUMN llm_concerns JSONB DEFAULT '[]';
ALTER TABLE matches ADD COLUMN judged_at TIMESTAMPTZ;

CREATE INDEX idx_matches_llm_score ON matches(llm_score DESC) WHERE llm_score IS NOT NULL;
