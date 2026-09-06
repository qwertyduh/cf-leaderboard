-- 007_problems: per-problem catalog (set / slot / theme / Learn More)
-- Run this after 001_tables.sql through 006_engagement.sql.
--
-- Adds the organizer-maintained problem catalog that the contest doc leans on:
--   * §4.1 scoring - base points are a function of (set, slot), so the fetcher
--     needs each problem's set+slot to score it (see fetcher/scoring.py).
--   * §3.3 / §5.4 problem index - title, theme, and the "Learn More" footer
--     links are rendered by the frontend problem index.
--
-- One row per (contest, problem_index).  Seeded by organizers via the Supabase
-- SQL editor (there is no admin UI yet - see README for an INSERT example).

CREATE TABLE problems (
    id            uuid     PRIMARY KEY DEFAULT gen_random_uuid(),
    contest_id    uuid     NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
    problem_index text     NOT NULL,   -- CF index, e.g. 'A', 'B', 'C1'
    problem_set   text     NOT NULL CHECK (problem_set IN ('A', 'B', 'C')),
    slot          smallint NOT NULL CHECK (slot BETWEEN 1 AND 8),
    title         text,
    theme         text,
    link          text,                -- URL to the problem statement
    learn_more    jsonb    NOT NULL DEFAULT '[]'::jsonb,  -- [{"label","url"}]

    UNIQUE (contest_id, problem_index)
);

CREATE INDEX idx_problems_contest ON problems(contest_id);

-- ── RLS: public read-only, same pattern as 002_rls.sql ─────────────────────
ALTER TABLE problems ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon can select problems"
    ON problems FOR SELECT TO anon USING (true);

CREATE POLICY "authenticated can select problems"
    ON problems FOR SELECT TO authenticated USING (true);

-- No write policies: organizers seed this via the service_role (SQL editor),
-- which bypasses RLS.
