"""cf-leaderboard fetcher - pulls Codeforces data and writes to Supabase.

Design (per docs/contest-documentation.md §4, §5):

* **contest.status is the scoring source (§5.2).**  Every judged submission
  (accepted *and* rejected) is ingested into the ``submissions`` table.  The
  ``problem_results`` table is a *deterministic projection* recomputed from
  those stored submissions - so a re-run, a formula change, or a CSV import
  (``recompute.py``, §5.3) all produce identical, re-runnable results (§13).
* **contest.standings is used only for metadata** - contest name / start /
  duration and the participant roster for ``contests.txt`` contests.  It is no
  longer the source of solved / wrong-submission data.
* **Scoring is the §4 model** - base points from each problem's ``(set, slot)``
  tag in the ``problems`` table, ``max(0.4, 1 - 0.15·W)`` decay with compilation
  errors excluded, and graduated 1.20 / 1.12 / 1.06 first-solver multipliers.
"""

import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from supabase import Client, create_client

from scoring import compute_score
from cf_auth import build_signed_url

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

CF_BASE_URL = "https://codeforces.com/api"
RATE_LIMIT_SECONDS = 2.0
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

STATUS_PAGE_SIZE = 1000   # contest.status rows per page
MAX_STATUS_PAGES = 50     # safety cap on a single contest's status scan

# Verdicts that count as a "wrong submission" for decay (§4.2) and the
# total-wrong tiebreaker (§4.4).  COMPILATION_ERROR is deliberately absent -
# the doc excludes compile errors.  Anything not listed here and not "OK"
# (TESTING, SKIPPED, etc.) is ignored.
WRONG_VERDICTS = frozenset(
    {
        "WRONG_ANSWER",
        "TIME_LIMIT_EXCEEDED",
        "RUNTIME_ERROR",
        "MEMORY_LIMIT_EXCEEDED",
        "IDLENESS_LIMIT_EXCEEDED",
        "PRESENTATION_ERROR",
        "CHALLENGED",
        "REJECTED",
        "PARTIAL",
        "FAILED",
    }
)

# ---------------------------------------------------------------------------
# logging
# ---------------------------------------------------------------------------


def setup_logging() -> logging.Logger:
    """Configure and return the module-level logger."""
    _logger = logging.getLogger("cf-fetcher")
    _logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    _logger.addHandler(console)

    # Suppress noisy third-party loggers.
    for name in ("supabase", "httpx", "urllib3", "httpcore", "hpack"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return _logger


logger = setup_logging()

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Load Supabase + optional Codeforces credentials from .env."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment. "
            f"Checked .env at: {env_path}"
        )

    return {
        "SUPABASE_URL": url,
        "SUPABASE_SERVICE_KEY": key,
        "CF_API_KEY": os.environ.get("CF_API_KEY", ""),
        "CF_API_SECRET": os.environ.get("CF_API_SECRET", ""),
    }


def init_supabase(url: str, service_key: str) -> Client:
    """Create and return a Supabase client using the service_role key."""
    return create_client(url, service_key)


# ---------------------------------------------------------------------------
# input files
# ---------------------------------------------------------------------------


def load_handles(filepath: Path) -> list[str]:
    """Read CF handles from a text file, one per line (lowercased, deduped)."""
    if not filepath.exists():
        raise RuntimeError(f"Handles file not found: {filepath}")

    raw = filepath.read_text(encoding="utf-8").splitlines()
    handles: list[str] = []
    for line in raw:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        handles.append(stripped.lower())

    seen: set[str] = set()
    unique: list[str] = []
    for h in handles:
        if h not in seen:
            seen.add(h)
            unique.append(h)

    if not unique:
        raise RuntimeError(f"No valid handles found in {filepath}")

    return unique


def load_contest_ids(filepath: Path) -> list[int]:
    """Read CF contest IDs from a text file, one per line (optional file)."""
    if not filepath.exists():
        logger.info("Contests file not found (%s) - skipping", filepath)
        return []

    raw = filepath.read_text(encoding="utf-8").splitlines()
    ids: list[int] = []
    for line in raw:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            ids.append(int(stripped))
        except ValueError:
            logger.warning(
                "Invalid contest ID in %s: %r - skipping", filepath, stripped
            )

    if not ids:
        logger.warning("No valid contest IDs found in %s", filepath)
    return ids


# ---------------------------------------------------------------------------
# Codeforces API
# ---------------------------------------------------------------------------

_last_request_time: float = 0.0


def _rate_limit_wait() -> None:
    """Sleep if necessary to enforce the global CF rate limit."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)


def cf_api_request(url: str, session: requests.Session) -> Optional[dict]:
    """Make a rate-limited, retrying GET request to the Codeforces API.

    Returns the ``result`` field of the JSON envelope, or ``None`` on failure.
    """
    global _last_request_time

    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(MAX_RETRIES):
        _rate_limit_wait()

        try:
            logger.debug("GET %s", url)
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            _last_request_time = time.monotonic()
        except (requests.Timeout, requests.ConnectionError) as exc:
            _last_request_time = time.monotonic()
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Request failed (%s), retrying in %ds (attempt %d/%d): %s",
                    exc.__class__.__name__,
                    wait,
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                )
                time.sleep(wait)
                continue
            logger.error("All %d retries exhausted for: %s", MAX_RETRIES, url)
            return None

        if resp.status_code in retryable_statuses:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "HTTP %d, retrying in %ds (attempt %d/%d): %s",
                    resp.status_code,
                    wait,
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                )
                time.sleep(wait)
                continue
            logger.error(
                "HTTP %d after %d retries, giving up: %s",
                resp.status_code,
                MAX_RETRIES,
                url,
            )
            return None

        try:
            data = resp.json()
        except ValueError:
            logger.error("Invalid JSON response from: %s", url)
            return None

        if data.get("status") != "OK":
            comment = data.get("comment", "no comment")
            logger.warning("CF API returned FAILED: %s (url: %s)", comment, url)
            return None

        return data["result"]

    return None


def fetch_user_ratings(
    handle: str, session: requests.Session
) -> Optional[list[dict]]:
    """Fetch a user's contest-rating history from Codeforces."""
    url = f"{CF_BASE_URL}/user.rating?handle={handle}"
    result = cf_api_request(url, session)
    if result is None:
        logger.warning("Could not fetch rating history for handle: %s", handle)
    return result


def fetch_contest_standings(
    contest_id: int,
    session: requests.Session,
    authenticated: bool = False,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
) -> Optional[dict]:
    """Fetch contest standings - used for metadata and roster only (§5.2).

    When ``authenticated`` is true the request is signed via
    :func:`cf_auth.build_signed_url` (required for mashup contests).
    """
    if authenticated:
        if not api_key or not api_secret:
            logger.warning(
                "Cannot fetch standings for mashup contest %d: "
                "CF_API_KEY / CF_API_SECRET not configured",
                contest_id,
            )
            return None
        url = build_signed_url(
            "contest.standings", {"contestId": contest_id}, api_key, api_secret
        )
    else:
        url = f"{CF_BASE_URL}/contest.standings?contestId={contest_id}"

    result = cf_api_request(url, session)
    if result is None:
        logger.warning("Could not fetch standings for contest %d", contest_id)
    return result


def build_status_url(
    contest_id: int,
    from_idx: int,
    count: int,
    authenticated: bool,
    api_key: Optional[str],
    api_secret: Optional[str],
) -> Optional[str]:
    """Build a (possibly signed) ``contest.status`` URL, or ``None`` if a
    mashup is requested without credentials."""
    if authenticated:
        if not api_key or not api_secret:
            return None
        return build_signed_url(
            "contest.status",
            {"contestId": contest_id, "from": from_idx, "count": count},
            api_key,
            api_secret,
        )
    return (
        f"{CF_BASE_URL}/contest.status"
        f"?contestId={contest_id}&from={from_idx}&count={count}"
    )


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------


def upsert_user(
    supabase: Client, cf_handle: str, display_name: Optional[str]
) -> Optional[str]:
    """Insert or update a user row.  Returns the user's UUID or ``None``."""
    try:
        resp = (
            supabase.table("users")
            .upsert(
                {"cf_handle": cf_handle, "display_name": display_name or cf_handle},
                on_conflict="cf_handle",
            )
            .execute()
        )
        row = resp.data[0] if resp.data else None
        if row:
            return row["id"]
    except Exception:
        logger.exception("Failed to upsert user: %s", cf_handle)
    return None


def upsert_contest(
    supabase: Client,
    cf_contest_id: int,
    name: str,
    start_time_seconds: int,
    duration_seconds: int,
) -> Optional[str]:
    """Insert or update a contest row.  Returns the contest's UUID or ``None``."""
    start_iso = datetime.fromtimestamp(
        start_time_seconds, tz=timezone.utc
    ).isoformat()
    try:
        resp = (
            supabase.table("contests")
            .upsert(
                {
                    "cf_contest_id": cf_contest_id,
                    "name": name,
                    "start_time": start_iso,
                    "duration_seconds": duration_seconds,
                },
                on_conflict="cf_contest_id",
            )
            .execute()
        )
        row = resp.data[0] if resp.data else None
        if row:
            return row["id"]
    except Exception:
        logger.exception("Failed to upsert contest: %d (%s)", cf_contest_id, name)
    return None


def upsert_problem_results_batch(supabase: Client, rows: list[dict]) -> int:
    """Batch-upsert problem_results rows.  Returns count upserted."""
    if not rows:
        return 0
    try:
        resp = (
            supabase.table("problem_results")
            .upsert(rows, on_conflict="user_id,contest_id,problem_index")
            .execute()
        )
        return len(resp.data) if resp.data else 0
    except Exception:
        logger.exception("Failed to batch-upsert %d problem_results", len(rows))
        return 0


def upsert_submissions_batch(supabase: Client, rows: list[dict]) -> int:
    """Batch-upsert submissions rows.  Returns count upserted."""
    if not rows:
        return 0
    try:
        resp = (
            supabase.table("submissions")
            .upsert(rows, on_conflict="id")
            .execute()
        )
        return len(resp.data) if resp.data else 0
    except Exception:
        logger.exception("Failed to batch-upsert %d submissions", len(rows))
        return 0


def write_fetch_log(
    supabase: Client,
    status: str,
    contests_processed: int,
    error: Optional[str],
    source: Optional[str] = None,
) -> None:
    """Write a row to the fetch_log table."""
    try:
        row: dict = {"status": status, "contests_processed": contests_processed}
        if error:
            row["error"] = error
        if source:
            row["source"] = source
        supabase.table("fetch_log").insert(row).execute()
        logger.info(
            "fetch_log written: source=%s, status=%s, contests=%d",
            source or "-",
            status,
            contests_processed,
        )
    except Exception:
        logger.exception("Failed to write fetch_log")


# ---------------------------------------------------------------------------
# caches
# ---------------------------------------------------------------------------


def preload_caches(
    supabase: Client,
) -> tuple[dict[str, str], dict[int, str]]:
    """Bulk-load existing users and contests from the DB into memory."""
    user_cache: dict[str, str] = {}
    contest_cache: dict[int, str] = {}

    try:
        resp = supabase.table("users").select("id,cf_handle").execute()
        for row in resp.data or []:
            user_cache[row["cf_handle"]] = row["id"]
        logger.info("Preloaded %d user(s) from DB", len(user_cache))
    except Exception:
        logger.exception("Failed to preload users cache")

    try:
        resp = supabase.table("contests").select("id,cf_contest_id").execute()
        for row in resp.data or []:
            contest_cache[row["cf_contest_id"]] = row["id"]
        logger.info("Preloaded %d contest(s) from DB", len(contest_cache))
    except Exception:
        logger.exception("Failed to preload contests cache")

    return user_cache, contest_cache


def preload_problem_catalog(
    supabase: Client,
) -> dict[tuple[str, str], dict]:
    """Load the ``problems`` catalog: ``{(contest_uuid, index): {set, slot}}``.

    Used to look up each problem's §4.1 base-points tag when scoring.
    """
    catalog: dict[tuple[str, str], dict] = {}
    try:
        resp = (
            supabase.table("problems")
            .select("contest_id,problem_index,problem_set,slot")
            .execute()
        )
        for row in resp.data or []:
            catalog[(row["contest_id"], row["problem_index"])] = {
                "problem_set": row.get("problem_set"),
                "slot": row.get("slot"),
            }
        logger.info("Preloaded %d problem catalog entr(ies)", len(catalog))
    except Exception:
        # The problems table may not exist yet (007 not run) - scoring falls
        # back to DEFAULT_BASE, so this is non-fatal.
        logger.warning(
            "Could not preload problem catalog (has 007_problems.sql run?) - "
            "scoring will use default base points"
        )
    return catalog


# ---------------------------------------------------------------------------
# metadata sync (standings → contest row + roster)
# ---------------------------------------------------------------------------


def sync_contest_metadata(
    supabase: Client,
    contest_id: int,
    fallback_name: str,
    register_all_participants: bool,
    session: requests.Session,
    user_cache: dict[str, str],
    contest_cache: dict[int, str],
    authenticated: bool = False,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
) -> Optional[str]:
    """Upsert the contest row (and, optionally, its full roster) from standings.

    Standings are used **only** for metadata + roster here (§5.2) - no
    solved/wrong data is derived from them.  Returns the contest UUID or ``None``.
    """
    cf_data = fetch_contest_standings(
        contest_id, session, authenticated, api_key, api_secret
    )
    if cf_data is None:
        return None

    contest_info = cf_data.get("contest")
    if not contest_info:
        logger.warning(
            "Contest %d: standings response missing 'contest' key", contest_id
        )
        return None

    contest_name = contest_info.get("name", fallback_name) or fallback_name
    contest_uuid = upsert_contest(
        supabase,
        cf_contest_id=contest_id,
        name=contest_name,
        start_time_seconds=contest_info.get("startTimeSeconds", 0),
        duration_seconds=contest_info.get("durationSeconds", 0),
    )
    if not contest_uuid:
        logger.warning("Contest %d: contest upsert failed", contest_id)
        return None
    contest_cache[contest_id] = contest_uuid

    if register_all_participants:
        rows = cf_data.get("rows", [])
        registered = 0
        for row in rows:
            members = row.get("party", {}).get("members", [])
            if not members:
                continue
            handle = members[0].get("handle", "").lower()
            if not handle or handle in user_cache:
                continue
            uid = upsert_user(supabase, handle, members[0].get("handle"))
            if uid:
                user_cache[handle] = uid
                registered += 1
        logger.info(
            "Contest %d (%s): metadata synced, %d participant(s), %d new user(s)",
            contest_id,
            contest_name,
            len(rows),
            registered,
        )
    else:
        logger.info("Contest %d (%s): metadata synced", contest_id, contest_name)

    return contest_uuid


# ---------------------------------------------------------------------------
# submission ingestion (contest.status → submissions table)
# ---------------------------------------------------------------------------


def latest_stored_submission_id(supabase: Client, contest_uuid: str) -> int:
    """Return the highest CF submission id already stored for a contest (0 if none)."""
    try:
        resp = (
            supabase.table("submissions")
            .select("id")
            .eq("contest_id", contest_uuid)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return int(rows[0]["id"]) if rows else 0
    except Exception:
        logger.exception(
            "Could not read latest stored submission id for contest %s",
            contest_uuid,
        )
        return 0


def ingest_contest_submissions(
    supabase: Client,
    cf_contest_id: int,
    contest_uuid: str,
    tracked_handles: Optional[set[str]],
    session: requests.Session,
    user_cache: dict[str, str],
    authenticated: bool,
    api_key: Optional[str],
    api_secret: Optional[str],
) -> tuple[int, set[str]]:
    """Ingest new judged submissions (any verdict) from ``contest.status``.

    Pages newest-first and stops once it reaches submissions already stored
    (id <= high-watermark), so steady-state runs are cheap.  ``tracked_handles``
    of ``None`` means "store every participant" (contests.txt mode).

    Returns ``(submissions_ingested, affected_problem_indexes)``.
    """
    watermark = latest_stored_submission_id(supabase, contest_uuid)
    ingested = 0
    affected: set[str] = set()
    from_idx = 1
    pages = 0
    reached_known = False

    while pages < MAX_STATUS_PAGES and not reached_known:
        url = build_status_url(
            cf_contest_id,
            from_idx,
            STATUS_PAGE_SIZE,
            authenticated,
            api_key,
            api_secret,
        )
        if url is None:
            logger.warning(
                "Skipping contest.status for mashup contest %d: "
                "CF_API_KEY / CF_API_SECRET not configured",
                cf_contest_id,
            )
            break

        result = cf_api_request(url, session)
        if result is None or not result:
            break

        batch_rows: list[dict] = []
        for sub in result:
            sub_id = sub.get("id")
            if sub_id is None:
                continue
            if sub_id <= watermark:
                reached_known = True
                continue

            verdict = sub.get("verdict")
            # Skip not-yet-judged submissions; they'll appear finalized later.
            if verdict in (None, "TESTING", "SUBMITTED"):
                continue

            author = sub.get("author", {})
            members = author.get("members", [])
            if not members:
                continue
            handle = members[0].get("handle", "").lower()
            if not handle:
                continue
            if tracked_handles is not None and handle not in tracked_handles:
                continue

            user_uuid = user_cache.get(handle)
            if user_uuid is None:
                user_uuid = upsert_user(supabase, handle, members[0].get("handle"))
                if user_uuid:
                    user_cache[handle] = user_uuid
                else:
                    continue

            problem_index = sub.get("problem", {}).get("index", "")
            if not problem_index:
                continue

            batch_rows.append(
                {
                    "id": sub_id,
                    "user_id": user_uuid,
                    "contest_id": contest_uuid,
                    "problem_index": problem_index,
                    "verdict": verdict,
                    "creation_time_seconds": sub.get("creationTimeSeconds", 0),
                }
            )
            affected.add(problem_index)

        if batch_rows:
            ingested += upsert_submissions_batch(supabase, batch_rows)

        pages += 1
        from_idx += STATUS_PAGE_SIZE

    if pages >= MAX_STATUS_PAGES and not reached_known:
        logger.warning(
            "Contest %d: hit MAX_STATUS_PAGES (%d) before catching up - "
            "older submissions may be unread this run",
            cf_contest_id,
            MAX_STATUS_PAGES,
        )
    if ingested:
        logger.info(
            "Contest %d: ingested %d new submission(s) across %d problem(s)",
            cf_contest_id,
            ingested,
            len(affected),
        )
    return ingested, affected


# ---------------------------------------------------------------------------
# recompute problem_results from stored submissions (deterministic projection)
# ---------------------------------------------------------------------------


def _wrong_before_ac(subs_sorted: list[dict], first_ac: Optional[int]) -> int:
    """Count non-CE wrong submissions before the first AC (or all, if unsolved)."""
    n = 0
    for s in subs_sorted:
        if s["verdict"] not in WRONG_VERDICTS:
            continue
        if first_ac is not None and s["creation_time_seconds"] >= first_ac:
            continue
        n += 1
    return n


def recompute_contest_results(
    supabase: Client,
    contest_uuid: str,
    problem_indexes: set[str],
    catalog: dict[tuple[str, str], dict],
) -> int:
    """Recompute ``problem_results`` for the given problems from stored subs.

    This is the single source of scoring truth (§4).  It reads every stored
    submission for each ``(contest, problem)``, derives solved / wrong-before-AC
    / first-AC time per user, ranks solvers by first-AC time to assign
    ``solve_order`` (§4.3), and writes the §4 score.  Idempotent and
    re-runnable - the CSV fallback (recompute.py, §5.3) calls this too.

    Returns the number of ``problem_results`` rows upserted.
    """
    updated = 0

    for problem_index in sorted(problem_indexes):
        try:
            resp = (
                supabase.table("submissions")
                .select("user_id,verdict,creation_time_seconds")
                .eq("contest_id", contest_uuid)
                .eq("problem_index", problem_index)
                .order("creation_time_seconds", desc=False)
                .execute()
            )
            subs = resp.data or []
        except Exception:
            logger.exception(
                "recompute: failed to read submissions for %s/%s",
                contest_uuid,
                problem_index,
            )
            continue

        if not subs:
            continue

        # Group submissions by user, preserving ascending time order.
        by_user: dict[str, list[dict]] = {}
        for s in subs:
            uid = s.get("user_id")
            if uid:
                by_user.setdefault(uid, []).append(s)

        # Per-user solve state.
        per_user: dict[str, dict] = {}
        for uid, user_subs in by_user.items():
            first_ac = next(
                (
                    s["creation_time_seconds"]
                    for s in user_subs
                    if s["verdict"] == "OK"
                ),
                None,
            )
            per_user[uid] = {
                "solved": first_ac is not None,
                "first_ac": first_ac,
                "wrong": _wrong_before_ac(user_subs, first_ac),
            }

        # Rank solvers by first-AC time → solve_order (§4.3).
        solvers = sorted(
            (uid for uid, d in per_user.items() if d["solved"]),
            key=lambda u: per_user[u]["first_ac"],
        )
        order_by_user = {uid: i + 1 for i, uid in enumerate(solvers)}

        tag = catalog.get((contest_uuid, problem_index), {})
        set_name = tag.get("problem_set")
        slot = tag.get("slot")

        rows: list[dict] = []
        for uid, d in per_user.items():
            solve_order = order_by_user.get(uid)  # None if unsolved
            score = compute_score(
                set_name=set_name,
                slot=slot,
                solve_order=solve_order,
                wrong_submissions=d["wrong"],
                solved=d["solved"],
            )
            rows.append(
                {
                    "user_id": uid,
                    "contest_id": contest_uuid,
                    "problem_index": problem_index,
                    "verdict": "OK" if d["solved"] else None,
                    "wrong_submissions": d["wrong"],
                    "solved": d["solved"],
                    "solve_order": solve_order,
                    "solve_rank": solve_order,
                    "score": score,
                }
            )

        updated += upsert_problem_results_batch(supabase, rows)

    if updated:
        logger.info(
            "recompute: %d problem_results row(s) updated across %d problem(s)",
            updated,
            len(problem_indexes),
        )
    return updated


def recompute_all(
    supabase: Client, catalog: Optional[dict[tuple[str, str], dict]] = None
) -> int:
    """Recompute every contest's ``problem_results`` from stored submissions.

    Used by the CSV fallback / full-recompute path (recompute.py, §5.3, §13).
    """
    if catalog is None:
        catalog = preload_problem_catalog(supabase)

    # Enumerate all (contest_uuid, problem_index) pairs that have submissions.
    try:
        resp = (
            supabase.table("submissions")
            .select("contest_id,problem_index")
            .execute()
        )
        rows = resp.data or []
    except Exception:
        logger.exception("recompute_all: failed to enumerate submissions")
        return 0

    by_contest: dict[str, set[str]] = {}
    for r in rows:
        by_contest.setdefault(r["contest_id"], set()).add(r["problem_index"])

    total = 0
    for contest_uuid, problem_indexes in by_contest.items():
        total += recompute_contest_results(
            supabase, contest_uuid, problem_indexes, catalog
        )
    logger.info("recompute_all: %d problem_results row(s) updated", total)
    return total


# ---------------------------------------------------------------------------
# leaderboard snapshot (rank-over-time + freeze source)
# ---------------------------------------------------------------------------


def write_leaderboard_snapshot(supabase: Client) -> int:
    """Snapshot the current standings into ``leaderboard_snapshots``.

    Reads the ``leaderboard`` view in its §4.4 tiebroken order and stores rank,
    score, and solved count per user.  This feeds both the rank-over-time graph
    (§6.2) and the leaderboard freeze (§4.5) - the frozen board is drawn from the
    snapshot taken at T+23h.
    """
    try:
        resp = (
            supabase.table("leaderboard")
            .select("user_id,total_score,problems_solved,total_wrong,last_ac_seconds")
            .order("total_score", desc=True)
            .order("total_wrong", desc=False)
            .order("last_ac_seconds", desc=False)
            .execute()
        )
        rows = resp.data or []
    except Exception:
        logger.exception("Failed to read leaderboard view for snapshot")
        return 0

    if not rows:
        return 0

    snapshot_rows = [
        {
            "user_id": row["user_id"],
            "rank": i + 1,
            "total_score": row["total_score"],
            "problems_solved": row.get("problems_solved", 0),
        }
        for i, row in enumerate(rows)
    ]

    try:
        supabase.table("leaderboard_snapshots").insert(snapshot_rows).execute()
    except Exception:
        logger.exception("Failed to write leaderboard_snapshots")
        return 0

    logger.info("Leaderboard snapshot written: %d row(s)", len(snapshot_rows))
    return len(snapshot_rows)


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def collect_contest_ids(
    handles: list[str], session: requests.Session
) -> dict[int, str]:
    """For every handle, fetch rating history and collect unique contests."""
    contests: dict[int, str] = {}
    for handle in handles:
        ratings = fetch_user_ratings(handle, session)
        if not ratings:
            if ratings is not None:
                logger.info("Handle %s has no rated contests - skipping", handle)
            continue
        for entry in ratings:
            cid = entry["contestId"]
            contests.setdefault(cid, entry["contestName"])
    if not contests:
        logger.warning(
            "No contests discovered - handles may be invalid or unrated."
        )
    return contests


def process_contest(
    supabase: Client,
    cf_contest_id: int,
    fallback_name: str,
    tracked_handles: Optional[set[str]],
    session: requests.Session,
    user_cache: dict[str, str],
    contest_cache: dict[int, str],
    catalog: dict[tuple[str, str], dict],
    authenticated: bool,
    api_key: Optional[str],
    api_secret: Optional[str],
) -> tuple[int, int]:
    """Full pipeline for one contest: metadata → ingest status → recompute.

    ``tracked_handles=None`` means "every participant" (contests.txt).
    Returns ``(submissions_ingested, problem_results_updated)``.
    """
    contest_uuid = sync_contest_metadata(
        supabase,
        cf_contest_id,
        fallback_name,
        register_all_participants=tracked_handles is None,
        session=session,
        user_cache=user_cache,
        contest_cache=contest_cache,
        authenticated=authenticated,
        api_key=api_key,
        api_secret=api_secret,
    )
    if not contest_uuid:
        return 0, 0

    ingested, affected = ingest_contest_submissions(
        supabase,
        cf_contest_id,
        contest_uuid,
        tracked_handles,
        session,
        user_cache,
        authenticated,
        api_key,
        api_secret,
    )

    updated = 0
    if affected:
        updated = recompute_contest_results(
            supabase, contest_uuid, affected, catalog
        )
    return ingested, updated


def main() -> None:
    """Run the full fetch-ingest-score pipeline for all tracked contests."""
    logger.info("=" * 60)
    logger.info("cf-leaderboard fetcher starting")

    config = load_config()
    supabase = init_supabase(config["SUPABASE_URL"], config["SUPABASE_SERVICE_KEY"])

    session = requests.Session()
    session.headers["User-Agent"] = "cf-leaderboard-fetcher/1.0"

    user_cache, contest_cache = preload_caches(supabase)
    catalog = preload_problem_catalog(supabase)

    handles = load_handles(Path(__file__).resolve().parent / "handles.txt")
    logger.info("Loaded %d handle(s): %s", len(handles), ", ".join(handles))
    tracked_handles: set[str] = set(handles)

    contest_ids = load_contest_ids(Path(__file__).resolve().parent / "contests.txt")
    if contest_ids:
        logger.info(
            "Loaded %d contest ID(s): %s",
            len(contest_ids),
            ", ".join(str(c) for c in contest_ids),
        )

    cf_api_key = config.get("CF_API_KEY") or None
    cf_api_secret = config.get("CF_API_SECRET") or None
    mashup_contest_ids: set[int] = set(contest_ids)
    if mashup_contest_ids and not (cf_api_key and cf_api_secret):
        logger.warning(
            "Mashup contests configured but CF_API_KEY / CF_API_SECRET missing "
            "- signed requests for %s will fail",
            mashup_contest_ids,
        )

    total_ingested = 0
    total_updated = 0
    total_contests = 0
    errors: list[str] = []

    # ── contests.txt path: the orientation mashup(s), all participants ──
    for cid in contest_ids:
        try:
            ing, upd = process_contest(
                supabase,
                cid,
                fallback_name="",
                tracked_handles=None,  # every participant
                session=session,
                user_cache=user_cache,
                contest_cache=contest_cache,
                catalog=catalog,
                authenticated=True,
                api_key=cf_api_key,
                api_secret=cf_api_secret,
            )
            total_ingested += ing
            total_updated += upd
            total_contests += 1
        except Exception as exc:
            logger.exception("[contests.txt] contest %d failed", cid)
            errors.append(f"{cid}: {exc.__class__.__name__}: {exc}")
    if contest_ids:
        write_fetch_log(
            supabase,
            "error" if errors else "success",
            total_contests,
            "\n".join(errors) if errors else None,
            source="contests.txt",
        )

    # ── handles.txt path: track specific users across public contests ──
    h_errors: list[str] = []
    if handles:
        try:
            discovered = collect_contest_ids(handles, session)
            for cid, cname in discovered.items():
                # Only ingest contests we don't already fully track via
                # contests.txt (avoid double work).
                if cid in mashup_contest_ids:
                    continue
                try:
                    ing, upd = process_contest(
                        supabase,
                        cid,
                        fallback_name=cname,
                        tracked_handles=tracked_handles,  # filter to our users
                        session=session,
                        user_cache=user_cache,
                        contest_cache=contest_cache,
                        catalog=catalog,
                        authenticated=False,  # public contests
                        api_key=None,
                        api_secret=None,
                    )
                    total_ingested += ing
                    total_updated += upd
                    total_contests += 1
                except Exception as exc:
                    logger.exception("[handles.txt] contest %d failed", cid)
                    h_errors.append(f"{cid}: {exc.__class__.__name__}: {exc}")
        except Exception as exc:
            logger.exception("[handles.txt] discovery failed")
            h_errors.append(f"discovery: {exc.__class__.__name__}: {exc}")
        write_fetch_log(
            supabase,
            "error" if h_errors else "success",
            total_contests,
            "\n".join(h_errors) if h_errors else None,
            source="handles.txt",
        )

    # ── leaderboard snapshot (rank-over-time + freeze source) ──
    snapshot_rows = 0
    try:
        snapshot_rows = write_leaderboard_snapshot(supabase)
    except Exception:
        logger.exception("Leaderboard snapshot step failed")

    overall = "error" if (errors or h_errors) else "success"
    logger.info(
        "Fetch complete: status=%s, contests=%d, submissions_ingested=%d, "
        "problem_results_updated=%d, snapshot_rows=%d",
        overall,
        total_contests,
        total_ingested,
        total_updated,
        snapshot_rows,
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
