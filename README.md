# cf-leaderboard

Codeforces leaderboard that pulls rating/standing data and displays it on a static frontend.

## Structure

```
cf-leaderboard/
  fetcher/           # Python scripts that pull CF data and write to Supabase
  frontend/          # static HTML/JS site that reads from Supabase
  supabase/          # SQL migration files
  .github/workflows/ # GitHub Actions scheduled fetcher
  .env.example       # template for required environment variables
```

## Setup

1. `cd fetcher && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your Supabase credentials.
   Public contests and `handles.txt`-driven calls need no CF key; fetching
   private/mashup contests (listed in `contests.txt`) requires `CF_API_KEY`
   and `CF_API_SECRET`.
3. Run the migrations in `supabase/` against your Supabase project:

   **Option A - Supabase Dashboard (easiest)**
   Open the [SQL Editor](https://supabase.com/dashboard/project/wrdwuzmjzcscolhjejtk/sql)
   and run the files **in order**:
   1. `supabase/001_tables.sql`
   2. `supabase/002_rls.sql`
   3. `supabase/003_view.sql`
   4. `supabase/004_fetch_log_source.sql`
   5. `supabase/005_submissions.sql`
   6. `supabase/006_engagement.sql`
   7. `supabase/007_problems.sql`
   8. `supabase/008_leaderboard_tiebreakers.sql`
   9. `supabase/009_snapshot_solved_reveal.sql`
   10. `supabase/010_hidden_challenges.sql`

   **Option B - psql (if you have the DB password)**
   ```bash
   for f in supabase/001_tables.sql supabase/002_rls.sql supabase/003_view.sql \
            supabase/004_fetch_log_source.sql supabase/005_submissions.sql \
            supabase/006_engagement.sql supabase/007_problems.sql \
            supabase/008_leaderboard_tiebreakers.sql \
            supabase/009_snapshot_solved_reveal.sql \
            supabase/010_hidden_challenges.sql; do
     psql "postgresql://postgres:<db-password>@db.wrdwuzmjzcscolhjejtk.supabase.co:5432/postgres" -f "$f"
   done
   ```

4. Add the CF handles you want to track in `fetcher/handles.txt` (one per line).
5. Add contest IDs you want to pull full standings from in `fetcher/contests.txt` (one per line).

## Running the fetcher

`main.py` runs one fetch+score cycle and exits - it's a one-shot script.
You have two options for running it regularly:

### Option A - GitHub Actions (recommended, free)

The repo includes `.github/workflows/fetch.yml` which runs every 15 minutes
via cron.  No laptop needed.

**Setup:**

1. Push this repo to GitHub (public or private - both work on the free tier)
2. Go to **Settings → Secrets and variables → Actions → New repository secret**
3. Add two secrets:

   | Name | Value |
   |---|---|
   | `SUPABASE_URL` | `https://wrdwuzmjzcscolhjejtk.supabase.co` |
   | `SUPABASE_SECRET_KEY` | Your service-role key from `.env` |

4. The workflow starts on the next cron tick.  You can trigger it immediately
   from the **Actions** tab → **Fetch CF Data** → **Run workflow**.

**Editing the handle / contest lists:** the workflow creates `handles.txt` and
`contests.txt` inline from the YAML - edit the lists in `.github/workflows/fetch.yml`
and push.

**⚠️ Disable the laptop loop once this is live** so you don't double-run:
```bash
screen -S cf-fetch -X quit
```
Or if you want to keep it as a backup, edit `run_loop.py` and set
`POLL_MINUTES` to something infrequent (e.g. 240) so it runs only a few
times a day.

### Option B - Laptop loop (screen)

```bash
cd fetcher
source .venv/bin/activate
screen -S cf-fetch python run_loop.py   # Ctrl-a d to detach
screen -r cf-fetch                      # reattach later
screen -S cf-fetch -X quit              # stop
```

## Deploying the frontend

`frontend/` is a zero-build static site - two files (`index.html` + `config.js`).
Any static host works.  The simplest free option:

### GitHub Pages

1. Push the repo to GitHub
2. Go to **Settings → Pages**
3. Set **Source** to **Deploy from a branch**, select `main`, folder `/frontend`
4. Click **Save** - your site is live at `https://<user>.github.io/cf-leaderboard/`

### Vercel / Netlify

Drag the `frontend/` folder onto [vercel.com](https://vercel.com) or
[netlify.com](https://netlify.com).  No config needed.

The anon key in `config.js` is safe to commit - RLS restricts the `anon`
role to `SELECT`-only on `users`, `contests`, `problem_results`, and the
`leaderboard` view.

## Contributing / day-to-day

### Adding a new handle to track

Add one line to `fetcher/handles.txt` (lowercase CF handle):

```
# fetcher/handles.txt
tourist
Benq
qwertyduh
new_user_here
```

If using GitHub Actions, also add the handle to `.github/workflows/fetch.yml`
in the `Create handles.txt` step (the inline heredoc).

### Tracking a new contest (all participants)

Add the numeric contest ID to `fetcher/contests.txt`:

```
# fetcher/contests.txt
2253
2254
```

This pulls every participant in that contest into the leaderboard, not
just the handles from `handles.txt`.  The contest ID is visible in the
CF URL: `https://codeforces.com/contest/2253` → ID is `2253`.

### Scoring model (contest doc §4)

Scoring lives in `fetcher/scoring.py` and implements the §4 model:

- **Base points** come from each problem's `(set, slot)` tag in the `problems`
  table (§4.1) - *not* the Codeforces problem rating. Set A / B / C and slots
  1–8 map to the fixed 100–600 table; set totals are 1150 / 2300 / 3450
  (max 6900).
- **Wrong-answer decay** `max(0.4, 1 - 0.15 · W)` (§4.2). Compilation errors
  are excluded - the fetcher counts wrong submissions from `contest.status`
  verdicts and skips `COMPILATION_ERROR`.
- **First-solver multiplier** 1.20 / 1.12 / 1.06 for the 1st / 2nd / 3rd solver
  of each problem (§4.3).

`problem_results` is a **deterministic projection** recomputed from the stored
`submissions` on every run, so a formula change just needs a recompute - no
manual row resets. After editing constants:

```bash
cd fetcher && source .venv/bin/activate
python -m pytest test_scoring.py -v   # verify the §4 model + worked example
python recompute.py                   # re-score every contest from stored subs
```

### Seeding the problem catalog (base points + problem index)

Scoring and the frontend problem index both read the `problems` table. Seed one
row per problem (get the contest UUID from `select id from contests where
cf_contest_id = <id>`):

```sql
insert into problems (contest_id, problem_index, problem_set, slot, title, theme, link, learn_more) values
  ('<contest-uuid>', 'A', 'A', 1, 'Hello, Fresher', 'JEE / pre-college',
   'https://codeforces.com/...',
   '[{"label":"print() basics","url":"https://www.geeksforgeeks.org/..."}]'),
  ('<contest-uuid>', 'B', 'A', 2, 'Attendance Shortage', 'campus life',
   'https://codeforces.com/...', '[]')
on conflict (contest_id, problem_index) do update
  set problem_set = excluded.problem_set, slot = excluded.slot,
      title = excluded.title, theme = excluded.theme,
      link = excluded.link, learn_more = excluded.learn_more;
```

Problems left untagged score at a safe default base (100) until you add them.

### Manual recompute / CSV fallback (contest doc §5.3)

`fetcher/recompute.py` is the mandatory override path. It rebuilds every
`problem_results` row from stored submissions and refreshes the leaderboard
snapshot - deterministic and re-runnable:

```bash
cd fetcher && source .venv/bin/activate
python recompute.py                 # recompute from stored submissions
python recompute.py --csv dump.csv  # import a CSV submission dump, then recompute
```

CSV header: `submission_id,handle,cf_contest_id,problem_index,verdict,creation_time_seconds`.
Use `--csv` when the live CF API path fails mid-contest - keep a fresh dump on
hand so the fallback is usable within ten minutes.

### Running the live-engagement features (announcements, schedule, predictions)

The frontend (`frontend/index.html`) reads three organizer-maintained tables
in addition to the leaderboard. There's no admin UI yet - seed and update
these directly in the Supabase SQL editor:

**Contest schedule** (drives the phase badge + countdown; one row per phase,
`phase` is one of `OPEN` / `SET_B` / `SET_C` / `FREEZE` / `REVEAL` / `CLOSE`).
The board **freezes** at `FREEZE` and shows the T+23h snapshot until `REVEAL`
(§4.5) - the live standings and per-problem grid stop updating in between. Omit
the `REVEAL` row and the board simply stays frozen after `FREEZE`.

```sql
insert into contest_schedule (phase, label, at_time) values
  ('OPEN',  'Set A opens',    '2026-09-01 10:00:00+05:30'),
  ('SET_B', 'Set B unlocks',  '2026-09-01 18:00:00+05:30'),
  ('SET_C', 'Set C unlocks',  '2026-09-01 23:00:00+05:30'),
  ('FREEZE','Board freezes',  '2026-09-02 09:00:00+05:30'),
  ('CLOSE', 'Contest closes', '2026-09-02 10:00:00+05:30'),
  ('REVEAL','Final standings','2026-09-02 11:00:00+05:30')
on conflict (phase) do update set label = excluded.label, at_time = excluded.at_time;
```

**Announcements** (pinned rows loop first in the judge-terminal ticker):

```sql
insert into announcements (body, pinned) values
  ('Welcome! Set A is live - A1 is a fixed-string warmup, go get your first AC.', true),
  ('14 people have solved A1 already.', false);
```

**Predictions** ("The Bookie's Table" - `options` is a JSON array of
`{"label": ..., "votes": ...}`; update `votes` by hand as the pool settles):

```sql
insert into predictions (question, options, sort_order) values
  ('Who reaches 10 solves first?',
   '[{"label":"tourist_wannabe","votes":9},{"label":"debug_addict","votes":4}]',
   1),
  ('Will C8 get solved at all?',
   '[{"label":"yes","votes":6},{"label":"no","votes":11}]',
   2);
```

Rank-over-time history needs no manual seeding - `fetcher/main.py` writes a
`leaderboard_snapshots` row per user on every run automatically, once
`006_engagement.sql` has been applied.

### Frontend site (newspaper design + tabs)

`frontend/index.html` is a tabbed, single-file site built to the editorial
"paper & ink" spec in `docs/design.md` (Leaderboard · Announcements · Info ·
Rules · Resources). Beyond the live leaderboard it has:

- **Countdown hero** - set the target in `frontend/config.js`:
  `var COUNTDOWN_TARGET = "2026-09-02T10:00:00+05:30";` (with `COUNTDOWN_LABEL`).
  Leave it `null` to fall back to `contest_schedule` (next upcoming phase, else
  `CLOSE`).
- **Top-5 movement graph** - the front-of-pack view of `leaderboard_snapshots`.
- **Hidden-challenge circles** - seed `hidden_challenges` (010), then flip `lit`
  by hand when a secret is cracked:

  ```sql
  insert into hidden_challenges (label, hint, sort_order) values
    ('Inspect Element', 'the source hides a door', 1),
    ('Assembled URL',   'outputs are fragments',   2);
  update hidden_challenges set lit = true, solved_by = 'qwertyduh', lit_at = now()
    where label = 'Inspect Element';
  ```
- **Resources tab** - edit the `RESOURCES` array near the top of the inline
  script in `index.html`.

### Running the test suite

```bash
cd fetcher
source .venv/bin/activate
python -m pytest test_scoring.py -v
```

### Checking the last few fetcher runs

```bash
cd fetcher
source .venv/bin/activate
python check_log.py            # last 10 runs
python check_log.py -n 5       # last 5
python check_log.py --watch    # refresh every 30 s
```

### Running a one-off fetch (no loop)

```bash
cd fetcher
source .venv/bin/activate
python main.py
```
