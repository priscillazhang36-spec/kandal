-- Add partner preference columns for cross-comparison matching
ALTER TABLE preferences ADD COLUMN partner_personality TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE preferences ADD COLUMN partner_values TEXT[] NOT NULL DEFAULT '{}';

NOTIFY pgrst, 'reload schema';
