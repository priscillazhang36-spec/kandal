-- Track position in the post-summary basics MCQ loop so we can resume after a gap.
ALTER TABLE profiling_conversations ADD COLUMN basics_index INT NOT NULL DEFAULT 0;

NOTIFY pgrst, 'reload schema';
