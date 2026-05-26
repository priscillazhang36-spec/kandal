-- Disable RLS on ideal_types to match the rest of the schema. Migration
-- 00022 created the table without explicit RLS handling, and Supabase
-- enabled RLS by default — production inserts from the backend (using
-- service_role) then failed with "new row violates row-level security
-- policy". This table is only written to by the backend, never by the
-- anon/authenticated client APIs, so RLS adds no real protection.
--
-- Matches the pattern used by profiles, onboarding_sessions,
-- profiling_conversations, etc.

ALTER TABLE ideal_types DISABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
