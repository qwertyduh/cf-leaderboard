// ---------------------------------------------------------------------------
// cf-leaderboard frontend config
// ---------------------------------------------------------------------------
//
// Why it's safe to expose the anon key here:
//
//   Row Level Security (RLS) is enabled on users, contests, problem_results,
//   and the leaderboard view.  The policies (002_rls.sql) only grant SELECT
//   to the 'anon' role - no INSERT, UPDATE, or DELETE.  The fetch_log table
//   has no SELECT policy for anon at all, so it's invisible from the browser.
//
//   The service_role key (SUPABASE_SECRET_KEY) is NEVER included in this
//   file - it lives server-side in .env and is used only by the fetcher.
//
//   Bottom line: the worst an attacker can do with this key is read the
//   leaderboard and problem data, which is the same thing the public website
//   already shows.  There's nothing private here.
// ---------------------------------------------------------------------------

var SUPABASE_URL = "https://wrdwuzmjzcscolhjejtk.supabase.co";
var SUPABASE_ANON_KEY = "sb_publishable_GOMh7WzL9wPBcnYY_fjt_A_0qTRQuHs";

// ---------------------------------------------------------------------------
// Countdown target
// ---------------------------------------------------------------------------
// The big hero countdown ticks down to this moment. Hardcode an ISO 8601
// timestamp here (include the timezone offset), OR leave it null to fall back
// to the contest_schedule table in Supabase - the countdown then targets the
// next upcoming phase (or CLOSE), whichever the DB says comes next.
//
//   Hardcoded example (10:00 IST, 2 Sep 2026):
//   var COUNTDOWN_TARGET = "2026-09-02T10:00:00+05:30";
var COUNTDOWN_TARGET = null;
var COUNTDOWN_LABEL = "until the contest closes";  // shown under the digits
