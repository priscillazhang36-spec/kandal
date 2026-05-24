-- Onboarding v4 — moment-elicitation conversation.
-- Each spark moment now carries a verbatim user-voice slice alongside the
-- paraphrased structured field. Storing as a single JSONB column keeps the
-- schema minimal while letting the LLM judge surface register/voice tells
-- that paraphrase strips out.
--
-- Shape:
--   {
--     "taste_fingerprint_quote": "...",
--     "current_obsession_quote": "...",
--     "humor_example_quote": "...",
--     "giving_quote": "...",
--     "pull_quote": "..."
--   }

ALTER TABLE profiles
    ADD COLUMN spark_voice JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Mirror on the test schema so the synthetic_test harness can exercise the
-- new verbatim path against Set A profiles.
ALTER TABLE test_profiles
    ADD COLUMN spark_voice JSONB NOT NULL DEFAULT '{}'::jsonb;

NOTIFY pgrst, 'reload schema';
