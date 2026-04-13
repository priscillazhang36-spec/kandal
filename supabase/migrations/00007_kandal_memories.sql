-- Per-user Kandal memory: persistent context that makes each Kandal feel
-- personal across sessions. Same brain (soul.md), different memories.

CREATE TABLE kandal_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('summary', 'fact', 'preference', 'feeling', 'episode')),
    content TEXT NOT NULL,
    salience REAL NOT NULL DEFAULT 0.5 CHECK (salience >= 0 AND salience <= 1),
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kandal_memories_recall
    ON kandal_memories (profile_id, salience DESC, created_at DESC);

-- Ongoing chat sessions (post-onboarding "1am text" conversations).
-- Distinct from profiling_conversations, which is the one-shot onboarding interview.
CREATE TABLE kandal_chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    messages JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_kandal_chats_profile ON kandal_chats(profile_id, updated_at DESC);
