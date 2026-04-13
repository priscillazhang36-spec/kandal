-- Embedding-based recall + decay tracking for Kandal memories.

ALTER TABLE kandal_memories ADD COLUMN embedding vector(512);
ALTER TABLE kandal_memories ADD COLUMN last_recalled_at TIMESTAMPTZ;
ALTER TABLE kandal_memories ADD COLUMN recall_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX idx_kandal_memories_embedding
    ON kandal_memories USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50)
    WHERE embedding IS NOT NULL;

-- Semantic recall with salience + exponential time decay.
-- effective_score = (0.6 * (1 - cos_dist) + 0.4 * salience) * exp(-age_days / half_life_days)
CREATE OR REPLACE FUNCTION recall_kandal_memories(
    p_profile_id UUID,
    p_query_embedding vector(512),
    p_limit INT DEFAULT 12,
    p_half_life_days REAL DEFAULT 30.0
)
RETURNS TABLE (
    id UUID,
    kind TEXT,
    content TEXT,
    salience REAL,
    score REAL
)
LANGUAGE SQL STABLE AS $$
    SELECT
        m.id,
        m.kind,
        m.content,
        m.salience,
        (
            (0.6 * (1.0 - (m.embedding <=> p_query_embedding))
             + 0.4 * m.salience)
            * EXP(- EXTRACT(EPOCH FROM (now() - m.created_at)) / 86400.0 / p_half_life_days)
        )::REAL AS score
    FROM kandal_memories m
    WHERE m.profile_id = p_profile_id
      AND m.embedding IS NOT NULL
    ORDER BY score DESC
    LIMIT p_limit;
$$;
