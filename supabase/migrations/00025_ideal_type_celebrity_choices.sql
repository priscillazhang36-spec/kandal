-- Celebrity forced-choice picks. Replaces the previous abstract `visual_type`
-- MCQ with 2-3 dynamically-generated celebrity pairs (filtered by
-- gender_preference + ethnicity_preference). Each user pick lands here as a
-- record with the original pair and which side they chose.
--
-- Shape:
--   [
--     {
--       "pair_index": 0,
--       "axis": "classic_vs_distinctive",
--       "a": {"name": "Henry Cavill", "descriptor": "..."},
--       "b": {"name": "Timothée Chalamet", "descriptor": "..."},
--       "picked": "a" | "b" | "neither",
--       "user_reply": "B — I think Timothée's vibe pulls me more"
--     },
--     ...
--   ]

ALTER TABLE ideal_types
    ADD COLUMN celebrity_choices JSONB NOT NULL DEFAULT '[]';

NOTIFY pgrst, 'reload schema';
