-- Photo-reveal gating. After Stage 3 LLM judge, matches sit in pending_review
-- until BOTH users opt in. Either declining drops the match silently —
-- the other side never learns it surfaced.
ALTER TABLE matches ADD COLUMN status TEXT NOT NULL DEFAULT 'pending_review';
ALTER TABLE matches ADD COLUMN response_a TEXT;     -- 'accepted' | 'declined' | NULL
ALTER TABLE matches ADD COLUMN response_b TEXT;     -- 'accepted' | 'declined' | NULL
ALTER TABLE matches ADD COLUMN responded_at_a TIMESTAMPTZ;
ALTER TABLE matches ADD COLUMN responded_at_b TIMESTAMPTZ;

CREATE INDEX idx_matches_status ON matches(status);

NOTIFY pgrst, 'reload schema';
