-- Track position + answers through the post-summary spark MCQ loop and the
-- long-term compatibility MCQ loop so we can resume after a gap.
ALTER TABLE profiling_conversations ADD COLUMN spark_index INT NOT NULL DEFAULT 0;
ALTER TABLE profiling_conversations ADD COLUMN longterm_index INT NOT NULL DEFAULT 0;
ALTER TABLE profiling_conversations ADD COLUMN longterm_answers JSONB NOT NULL DEFAULT '[]'::jsonb;

NOTIFY pgrst, 'reload schema';
