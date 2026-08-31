-- 008_leaderboard_tiebreakers: rank exactly per §4.4
-- Run this after 003_view.sql (redefines the same `leaderboard` view) and
-- 005_submissions.sql (needs the submissions table for the last-AC tiebreaker).
--
-- Doc §4.4 ranking order:
--   1. total score            — descending
--   2. total wrong submissions — ascending  (fewer negatives ranks higher)
--   3. timestamp of last scoring submission — ascending
--
-- The old view (003) ordered by total_score only.  This adds the two missing
-- tiebreakers and the columns they need (total_wrong, last_ac_seconds) so the
-- frontend and the snapshot writer can rank identically.

CREATE OR REPLACE VIEW leaderboard AS
SELECT
    u.id                                    AS user_id,
    u.cf_handle,
    u.display_name,
    COALESCE(SUM(pr.score), 0)              AS total_score,
    COUNT(pr.id) FILTER (WHERE pr.solved)   AS problems_solved,
    COALESCE(SUM(pr.wrong_submissions), 0)  AS total_wrong,
    la.last_ac_seconds                      AS last_ac_seconds
FROM users u
LEFT JOIN problem_results pr ON pr.user_id = u.id
LEFT JOIN (
    -- Timestamp of each user's most recent accepted ("scoring") submission.
    SELECT user_id, MAX(creation_time_seconds) AS last_ac_seconds
    FROM submissions
    WHERE verdict = 'OK'
    GROUP BY user_id
) la ON la.user_id = u.id
GROUP BY u.id, u.cf_handle, u.display_name, la.last_ac_seconds
ORDER BY
    total_score DESC,
    total_wrong ASC,
    last_ac_seconds ASC NULLS LAST;

-- CREATE OR REPLACE preserves existing grants, but re-assert them so this file
-- is safe to run standalone.
GRANT SELECT ON leaderboard TO anon;
GRANT SELECT ON leaderboard TO authenticated;
