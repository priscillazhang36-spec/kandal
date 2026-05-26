-- Visual preference fields on ideal_types. Captured via two Stage 0 MCQs:
--   visual_type        — categorical bucket (classic/artsy/athletic/no_strong_type),
--                        mirrors preferences.visual_type from full_discovery.
--   visual_importance  — how much looks actually matter to the user
--                        (high/secondary/low/open). Useful signal because some
--                        users barely register visuals — others lead with them.

ALTER TABLE ideal_types
    ADD COLUMN visual_type TEXT,
    ADD COLUMN visual_importance TEXT;

NOTIFY pgrst, 'reload schema';
