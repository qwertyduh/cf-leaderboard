-- 005_submissions: per-submission timing + solve_rank
-- Run this after 001_tables.sql through 004_fetch_log_source.sql.

-- ── submissions ─────────────────────────────────────────────────────────────
-- One row per accepted Codeforces submission from a tracked user.  The CF
-- submission id is the primary key (and dedup key) - re-fetching during the
-- 20-minute sliding window is a harmless no-op.
CREATE TABLE submissions (
    id                    int PRIMARY KEY,   -- CF submission ID (dedup key)
    user_id               uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contest_id            uuid NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
    problem_index         text NOT NULL,
    verdict               text,
    creation_time_seconds int NOT NULL,
    fetched_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_submissions_user    ON submissions(user_id);
CREATE INDEX idx_submissions_contest ON submissions(contest_id);
-- Speed up solve_rank recomputation: order accepted submissions per problem.
CREATE INDEX idx_submissions_cp      ON submissions(contest_id, problem_index, creation_time_seconds);

-- ── solve_rank on problem_results ───────────────────────────────────────────
-- 1 = first tracked user to solve that problem in that contest,
-- 2 = second, etc.  NULL until computed by the submissions step.
ALTER TABLE problem_results ADD COLUMN solve_rank int;

-- ── RLS ─────────────────────────────────────────────────────────────────────
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon can select submissions"
    ON submissions FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "authenticated can select submissions"
    ON submissions FOR SELECT
    TO authenticated
    USING (true);
