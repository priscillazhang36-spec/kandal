-- Add experiment_run column to test_matches so multiple prompt variants
-- (e.g. 'spark_first_v1', 'spark_first_v2', 'spark_first_v3') can coexist
-- for the same (profile_a, profile_b, model) tuple.
--
-- Existing rows are backfilled to 'baseline'; the unique constraint is
-- extended to include experiment_run.

ALTER TABLE test_matches
    ADD COLUMN experiment_run TEXT NOT NULL DEFAULT 'baseline';

ALTER TABLE test_matches
    DROP CONSTRAINT test_matches_profile_a_id_profile_b_id_model_key;

ALTER TABLE test_matches
    ADD CONSTRAINT test_matches_profile_a_id_profile_b_id_model_experiment_run_key
    UNIQUE (profile_a_id, profile_b_id, model, experiment_run);

CREATE INDEX idx_test_matches_experiment_run ON test_matches(experiment_run);

NOTIFY pgrst, 'reload schema';
