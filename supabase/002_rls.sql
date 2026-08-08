-- 002_rls: Row Level Security policies
-- Run this after 001_tables.sql.

-- Enable RLS on every table that faces the public API.
ALTER TABLE users           ENABLE ROW LEVEL SECURITY;
ALTER TABLE contests        ENABLE ROW LEVEL SECURITY;
ALTER TABLE problem_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE fetch_log       ENABLE ROW LEVEL SECURITY;

-- ── Public read-only access ────────────────────────────────────────────────
-- The frontend loads data using the Supabase anon key, which maps to the
-- 'anon' PostgreSQL role. These policies let anyone with the anon key
-- SELECT from these three tables but do nothing else.
--
-- We also add the same SELECT policy for 'authenticated' so that logged-in
-- Supabase users get the same read-only access out of the box.

-- users
CREATE POLICY "anon can select users"
    ON users FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "authenticated can select users"
    ON users FOR SELECT
    TO authenticated
    USING (true);

-- contests
CREATE POLICY "anon can select contests"
    ON contests FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "authenticated can select contests"
    ON contests FOR SELECT
    TO authenticated
    USING (true);

-- problem_results
CREATE POLICY "anon can select problem_results"
    ON problem_results FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "authenticated can select problem_results"
    ON problem_results FOR SELECT
    TO authenticated
    USING (true);

-- ── fetch_log is NOT exposed to anon / authenticated ───────────────────────
-- No SELECT policy exists on fetch_log for these roles, so public requests
-- see zero rows. Only the service_role (used by the fetcher) can read or
-- write it, because service_role bypasses RLS entirely by default.

-- ── No public write access ─────────────────────────────────────────────────
-- We deliberately add no INSERT, UPDATE, or DELETE policies on any table for
-- anon or authenticated. That means:
--
--   anon / authenticated  →  SELECT only (and only on the three tables above)
--   service_role          →  full access (bypasses all RLS)
--
-- The fetcher uses the SUPABASE_SERVICE_KEY, which maps to service_role, so
-- it can write freely. The frontend uses the anon key, which maps to anon,
-- so it can only read.
