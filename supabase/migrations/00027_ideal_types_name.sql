-- Add a top-level name column on ideal_types so the name captured at the
-- start of the ideal_type_discovery flow is queryable directly, instead of
-- buried inside the sub_state JSONB blob.

ALTER TABLE ideal_types ADD COLUMN name TEXT;

NOTIFY pgrst, 'reload schema';
