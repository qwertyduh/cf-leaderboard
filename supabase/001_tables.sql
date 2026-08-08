-- 001_tables: core schema for cf-leaderboard
-- Run this first, before 002_rls.sql and 003_view.sql.

-- ── users ──────────────────────────────────────────────────────────────────
-- One row per tracked Codeforces user. The fetcher upserts into this table
-- whenever it discovers a new handle. display_name is whatever the CF API
-- returns (or the handle itself as a fallback).
CREATE TABLE users (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    cf_handle   text        NOT NULL UNIQUE,
    display_name text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ── contests ───────────────────────────────────────────────────────────────
-- One row per Codeforces contest we've pulled. cf_contest_id is the numeric
-- ID the CF API uses (e.g. 2000 for a regular round).
CREATE TABLE contests (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    cf_contest_id    int         NOT NULL UNIQUE,
    name             text        NOT NULL,
    start_time       timestamptz NOT NULL,
    duration_seconds int         NOT NULL
);

-- ── problem_results ────────────────────────────────────────────────────────
-- One row per (user, contest, problem) tuple. The fetcher computes a custom
-- score and stores it here. solve_order is 1/2/3 for the first three people
-- to solve that particular problem (the "top-3 finish" bonus driver) and
-- NULL otherwise.
CREATE TABLE problem_results (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid        NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    contest_id        uuid        NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
    problem_index     text        NOT NULL,   -- e.g. 'A', 'B', 'C1'
    problem_rating    int,                    -- CF rating of the problem, if known
    verdict           text,                   -- CF verdict string (e.g. 'OK')
    wrong_submissions int         NOT NULL DEFAULT 0,
    solved            boolean     NOT NULL DEFAULT false,
    solve_order       smallint,               -- 1, 2, 3 for first solvers; NULL otherwise
    score             numeric     NOT NULL DEFAULT 0,
    computed_at       timestamptz NOT NULL DEFAULT now(),

    UNIQUE (user_id, contest_id, problem_index)
);

-- ── fetch_log ──────────────────────────────────────────────────────────────
-- Debug / audit log. The fetcher writes one row per run so you can see when
-- it last succeeded, how many contests it touched, and what broke.
CREATE TABLE fetch_log (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at             timestamptz NOT NULL DEFAULT now(),
    status             text        NOT NULL,  -- 'success' | 'error'
    contests_processed int         NOT NULL DEFAULT 0,
    error              text                    -- stack / message when status = 'error'
);

-- ── indexes ────────────────────────────────────────────────────────────────
-- Speed up the common fetcher lookups and the leaderboard join.
CREATE INDEX idx_problem_results_user    ON problem_results(user_id);
CREATE INDEX idx_problem_results_contest ON problem_results(contest_id);
CREATE INDEX idx_fetch_log_run_at        ON fetch_log(run_at DESC);
