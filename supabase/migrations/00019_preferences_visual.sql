-- Onboarding v4.1 — appearance preference dimension.
-- Captures what kind of look the user is visually pulled toward, both as a
-- freeform description (`visual_preference`) and a categorical bucket
-- (`visual_type`: classic / artsy / athletic / no_strong_type). Used by the
-- judge as a soft scoring factor; a future phase will tie it to photo-based
-- pre-filtering.
--
-- Mirrored on test_preferences for the synthetic_test harness.

ALTER TABLE preferences
    ADD COLUMN visual_preference TEXT,
    ADD COLUMN visual_type TEXT;

ALTER TABLE test_preferences
    ADD COLUMN visual_preference TEXT,
    ADD COLUMN visual_type TEXT;

NOTIFY pgrst, 'reload schema';
