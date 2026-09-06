-- 003_view: leaderboard view
-- Run this after 001_tables.sql (the RLS in 002_rls.sql is not required
-- before this view, but run them in numeric order).

-- ── leaderboard ────────────────────────────────────────────────────────────
-- One row per user, summing score across all problem_results. A user with
-- zero problem_results still appears (score 0).
CREATE VIEW leaderboard AS
SELECT
    u.id            AS user_id,
    u.cf_handle,
    u.display_name,
    COALESCE(SUM(pr.score), 0) AS total_score,
    COUNT(pr.id) FILTER (WHERE pr.solved) AS problems_solved
FROM users u
LEFT JOIN problem_results pr ON pr.user_id = u.id
GROUP BY u.id, u.cf_handle, u.display_name
ORDER BY total_score DESC;

-- ── Grant read access to public roles ──────────────────────────────────────
-- By default, views in PostgreSQL run with the permissions of their owner
-- (security definer). The owner is the role that ran CREATE VIEW - typically
-- postgres or the Superbase dashboard user - which bypasses RLS. That's
-- exactly what we want: the view aggregates across all rows, and we control
-- access via GRANT / REVOKE on the view itself.
GRANT SELECT ON leaderboard TO anon;
GRANT SELECT ON leaderboard TO authenticated;
