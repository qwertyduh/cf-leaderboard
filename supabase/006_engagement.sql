-- 006_engagement: live-engagement feature tables
-- Run this after 001_tables.sql through 005_submissions.sql.
--
-- Adds the data sources for the site features described in the contest
-- documentation (§5.4, §6): announcements ticker, release/freeze schedule,
-- the Bookie's Table prediction pool, and rank-over-time history.
--
-- All four tables follow the existing read-only pattern (002_rls.sql):
-- anon/authenticated get SELECT only. There is no public write path yet —
-- organizers seed and update these by hand via the Supabase SQL editor
-- (see README for examples), or the fetcher's service_role key writes
-- leaderboard_snapshots automatically on every run.

-- ── announcements ────────────────────────────────────────────────────────
-- Organizer-authored lines for the judge-terminal ticker. `pinned` rows are
-- shown first/looped; the rest scroll through in reverse-chronological order.
CREATE TABLE announcements (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    body       text        NOT NULL,
    pinned     boolean     NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ── contest_schedule ─────────────────────────────────────────────────────
-- One row per named phase boundary (§3.2). The frontend derives the current
-- phase badge and "time to next release" countdown by comparing now() to
-- these timestamps — no hardcoded dates in the frontend.
CREATE TABLE contest_schedule (
    id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    phase   text        NOT NULL UNIQUE,   -- 'OPEN' | 'SET_B' | 'SET_C' | 'FREEZE' | 'CLOSE'
    label   text        NOT NULL,          -- human label, e.g. "Set B unlocks"
    at_time timestamptz NOT NULL
);

-- ── predictions ──────────────────────────────────────────────────────────
-- "The Bookie's Table" (§6.3). Read-only display of prediction questions and
-- their current tallies; organizers update `options` by hand until a real
-- staking/write path exists.
CREATE TABLE predictions (
    id         uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    question   text    NOT NULL,
    options    jsonb   NOT NULL,           -- [{"label": "tourist", "votes": 12}, ...]
    closed     boolean NOT NULL DEFAULT false,
    sort_order smallint NOT NULL DEFAULT 0
);

-- ── leaderboard_snapshots ────────────────────────────────────────────────
-- One row per (user, poll) with that user's rank + score at that moment.
-- This is the data source for the rank-over-time graph (§6.2). Written
-- automatically by the fetcher's service_role client on every run
-- (see fetcher/main.py: write_leaderboard_snapshot).
CREATE TABLE leaderboard_snapshots (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    taken_at    timestamptz NOT NULL DEFAULT now(),
    user_id     uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rank        int         NOT NULL,
    total_score numeric     NOT NULL
);

CREATE INDEX idx_snapshots_taken_at ON leaderboard_snapshots(taken_at);
CREATE INDEX idx_snapshots_user     ON leaderboard_snapshots(user_id);

-- ── RLS ───────────────────────────────────────────────────────────────────
ALTER TABLE announcements         ENABLE ROW LEVEL SECURITY;
ALTER TABLE contest_schedule      ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaderboard_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon can select announcements" ON announcements FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated can select announcements" ON announcements FOR SELECT TO authenticated USING (true);

CREATE POLICY "anon can select contest_schedule" ON contest_schedule FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated can select contest_schedule" ON contest_schedule FOR SELECT TO authenticated USING (true);

CREATE POLICY "anon can select predictions" ON predictions FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated can select predictions" ON predictions FOR SELECT TO authenticated USING (true);

CREATE POLICY "anon can select leaderboard_snapshots" ON leaderboard_snapshots FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated can select leaderboard_snapshots" ON leaderboard_snapshots FOR SELECT TO authenticated USING (true);

-- No INSERT/UPDATE/DELETE policies for anon/authenticated on any of the
-- four tables above — same reasoning as 002_rls.sql. announcements,
-- contest_schedule, and predictions are organizer-maintained via the
-- Supabase dashboard; leaderboard_snapshots is fetcher-maintained via
-- service_role, which bypasses RLS.
