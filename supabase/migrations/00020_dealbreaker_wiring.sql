-- v4.2 — Wire the lifestyle basics into the matching dealbreaker.
--
-- Two coordinated changes:
--   1. Add 2 paired-tolerance columns to `preferences` (asks the user what
--      they'll accept FROM A PARTNER, not just their own state):
--        partner_wants_kids        — yes / no / open
--        partner_substances_max    — never / socially / regularly / open
--   2. Mirror the existing lifestyle-basics columns (00010) onto the
--      `test_preferences` table so the synthetic_test harness can run
--      dealbreakers against them — currently missing entirely.

-- Paired tolerance fields (prod + test)
ALTER TABLE preferences
    ADD COLUMN partner_wants_kids TEXT,
    ADD COLUMN partner_substances_max TEXT;

ALTER TABLE test_preferences
    ADD COLUMN partner_wants_kids TEXT,
    ADD COLUMN partner_substances_max TEXT;

-- Mirror prod lifestyle basics onto test schema (these were prod-only since 00010)
ALTER TABLE test_preferences
    ADD COLUMN relationship_intent TEXT,
    ADD COLUMN has_kids TEXT,
    ADD COLUMN wants_kids TEXT,
    ADD COLUMN relationship_structure TEXT,
    ADD COLUMN religion TEXT,
    ADD COLUMN religion_importance TEXT,
    ADD COLUMN drinks TEXT,
    ADD COLUMN smokes TEXT,
    ADD COLUMN cannabis TEXT;

NOTIFY pgrst, 'reload schema';
