-- 009_snapshot_solved_reveal: make snapshots self-sufficient for the freeze
-- Run this after 006_engagement.sql.
--
-- The leaderboard freeze (§4.5) shows the standings *as they stood at T+23h*
-- and stops updating until the reveal.  The frontend renders that frozen board
-- from the snapshot taken at the freeze, so a snapshot row must carry enough to
-- draw a leaderboard line on its own: rank, score, and solved count.  Rank and
-- score already exist; add problems_solved here.
ALTER TABLE leaderboard_snapshots
    ADD COLUMN problems_solved int NOT NULL DEFAULT 0;

-- Optional REVEAL phase for contest_schedule.  The board stays frozen from
-- FREEZE until REVEAL (final standings at T+25h, §4.5); if organizers omit the
-- REVEAL row the board simply stays frozen.  Documented here for clarity — no
-- schema change is needed since `phase` is free text, but the CHECK below keeps
-- typos out if you prefer to enforce the vocabulary.
--
-- (Left commented so it never conflicts with an existing constraint; enable it
-- if you want the DB to reject unknown phase names.)
--
-- ALTER TABLE contest_schedule
--     ADD CONSTRAINT contest_schedule_phase_check
--     CHECK (phase IN ('OPEN','SET_B','SET_C','FREEZE','REVEAL','CLOSE'));
