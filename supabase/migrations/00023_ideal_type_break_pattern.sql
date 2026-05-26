-- Separate break_pattern column on ideal_types so the readback can show
-- pull-side and break-side as two distinct sections. Previously break was
-- folded into pull_pattern; splitting them makes the artifact verifiable
-- field-by-field by the user.

ALTER TABLE ideal_types
    ADD COLUMN break_pattern TEXT;

NOTIFY pgrst, 'reload schema';
