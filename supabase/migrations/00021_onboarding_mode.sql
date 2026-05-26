-- Onboarding mode selector. Distinguishes the existing user-centric flow
-- (full_discovery, ~20 min, produces a match-ready profile) from the new
-- partner-clarity flow (ideal_type_discovery, <10 min, produces an ideal-type
-- artifact only). New default is ideal_type_discovery — full_discovery is
-- opt-in via the web client; SMS handler sets it explicitly.

ALTER TABLE onboarding_sessions
    ADD COLUMN mode TEXT NOT NULL DEFAULT 'ideal_type_discovery';

NOTIFY pgrst, 'reload schema';
