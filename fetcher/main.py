"""cf-leaderboard fetcher — pulls Codeforces data and writes to Supabase."""

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

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

CF_BASE_URL = "https://codeforces.com/api"
RATE_LIMIT_SECONDS = 2.0
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

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
    """Load SUPABASE_URL and SUPABASE_SECRET_KEY from .env in the project root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")

    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SECRET_KEY in environment. "
            f"Checked .env at: {env_path}"
        )

    return {"SUPABASE_URL": url, "SUPABASE_SERVICE_KEY": key}


def init_supabase(url: str, service_key: str) -> Client:
    """Create and return a Supabase client using the service_role key."""
    return create_client(url, service_key)


# ---------------------------------------------------------------------------
# handles file
# ---------------------------------------------------------------------------


def load_handles(filepath: Path) -> list[str]:
    """Read CF handles from a text file, one per line.

    Skips blank lines and lines starting with ``#``.  Returns lowercased,
    deduplicated handles.
    """
    if not filepath.exists():
        raise RuntimeError(f"Handles file not found: {filepath}")

    raw = filepath.read_text(encoding="utf-8").splitlines()
    handles: list[str] = []
    for line in raw:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        handles.append(stripped.lower())

    # Deduplicate while preserving order.
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
    """Read CF contest IDs from a text file, one per line.

    Skips blank lines and lines starting with ``#``.  Returns an empty
    list if the file is missing (making contests.txt optional).
    """
    if not filepath.exists():
        logger.info("Contests file not found (%s) — skipping", filepath)
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
                "Invalid contest ID in %s: %r — skipping", filepath, stripped
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
    """Make a rate-limited GET request to the Codeforces API.

    Retries up to ``MAX_RETRIES`` times on transient failures (timeouts,
    429, 5xx) with exponential backoff.  Returns the ``result`` field of
    the JSON envelope on success, or ``None`` on unrecoverable failure.
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
            logger.error(
                "All %d retries exhausted for: %s", MAX_RETRIES, url
            )
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

        # Parse the CF JSON envelope.
        try:
            data = resp.json()
        except ValueError:
            logger.error("Invalid JSON response from: %s", url)
            return None

        if data.get("status") != "OK":
            comment = data.get("comment", "no comment")
            logger.warning(
                "CF API returned FAILED: %s (url: %s)", comment, url
            )
            return None

        return data["result"]

    return None


def fetch_user_ratings(
    handle: str, session: requests.Session
) -> Optional[list[dict]]:
    """Fetch a user's contest-rating history from Codeforces.

    Returns:
        * A list of rating-change dicts on success.
        * An empty list when the handle is valid but has zero rated contests.
        * ``None`` when the API call itself failed.
    """
    url = f"{CF_BASE_URL}/user.rating?handle={handle}"
    result = cf_api_request(url, session)
    if result is None:
        logger.warning(
            "Could not fetch rating history for handle: %s", handle
        )
    return result


def fetch_contest_standings(
    contest_id: int, session: requests.Session
) -> Optional[dict]:
    """Fetch full contest standings (all participants).

    We intentionally do **not** pass ``handles`` or ``showUnofficial``
    because the CF API rejects extra parameters on non-gym contest
    standings for unauthenticated requests.  Callers must filter the
    returned rows down to the handles they care about.

    Returns the full ``result`` dict (keys: ``contest``, ``problems``,
    ``rows``) or ``None`` on failure.
    """
    url = f"{CF_BASE_URL}/contest.standings?contestId={contest_id}"
    result = cf_api_request(url, session)
    if result is None:
        logger.warning(
            "Could not fetch standings for contest %d", contest_id
        )
    return result


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
                {
                    "cf_handle": cf_handle,
                    "display_name": display_name or cf_handle,
                },
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
        logger.exception(
            "Failed to upsert contest: %d (%s)", cf_contest_id, name
        )
    return None


def upsert_problem_results_batch(
    supabase: Client, rows: list[dict]
) -> int:
    """Batch-upsert problem_results rows.  Returns count of rows upserted."""
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
        logger.exception(
            "Failed to batch-upsert %d problem_results", len(rows)
        )
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
        row: dict = {
            "status": status,
            "contests_processed": contests_processed,
        }
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


def compute_and_update_scores(supabase: Client) -> int:
    """Score every ``problem_results`` row that doesn't have a score yet.

    Queries rows where ``score = 0 AND solved = true``, calls the pure
    :func:`compute_score` function, and writes the result back.
    Unsolved rows always score 0, so we skip them entirely — no point
    re-scoring rows whose score will never change.

    Returns the number of rows that were updated.
    """
    try:
        resp = (
            supabase.table("problem_results")
            .select("id,problem_rating,solve_order,wrong_submissions,solved")
            .eq("score", 0)
            .eq("solved", True)
            .execute()
        )
        rows = resp.data or []
    except Exception:
        logger.exception("Failed to fetch unscored problem_results")
        return 0

    if not rows:
        logger.info("Scoring: no new rows to score")
        return 0

    updated = 0
    skipped = 0
    total_new_score = 0.0
    for row in rows:
        new_score = compute_score(
            problem_rating=row.get("problem_rating"),
            solve_order=row.get("solve_order"),
            wrong_submissions=row.get("wrong_submissions", 0),
            solved=row.get("solved", False),
        )
        try:
            (
                supabase.table("problem_results")
                .update({"score": new_score})
                .eq("id", row["id"])
                .execute()
            )
            updated += 1
            total_new_score += new_score
        except Exception:
            logger.exception(
                "Failed to update score for problem_results row %s",
                row["id"],
            )
            skipped += 1

    logger.info(
        "Scoring: %d row(s) updated, %d failed, total new score = %.1f",
        updated,
        skipped,
        total_new_score,
    )
    return updated


# ---------------------------------------------------------------------------
# cache preloading
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
        resp = (
            supabase.table("contests")
            .select("id,cf_contest_id")
            .execute()
        )
        for row in resp.data or []:
            contest_cache[row["cf_contest_id"]] = row["id"]
        logger.info("Preloaded %d contest(s) from DB", len(contest_cache))
    except Exception:
        logger.exception("Failed to preload contests cache")

    return user_cache, contest_cache


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def collect_contest_ids(
    handles: list[str],
    session: requests.Session,
) -> dict[int, str]:
    """For every handle, fetch rating history and collect unique contests.

    Returns ``{cf_contest_id: contest_name}``.
    """
    contests: dict[int, str] = {}

    for handle in handles:
        ratings = fetch_user_ratings(handle, session)
        if ratings is None:
            continue
        if not ratings:
            logger.info(
                "Handle %s has no rated contests — skipping", handle
            )
            continue

        for entry in ratings:
            cid = entry["contestId"]
            if cid not in contests:
                contests[cid] = entry["contestName"]

        logger.debug(
            "Handle %s: %d contest(s) in history", handle, len(ratings)
        )

    if not contests:
        logger.warning(
            "No contests discovered — all handles may be invalid "
            "or have no rating history."
        )
    return contests


def process_contest_standings(
    supabase: Client,
    contest_id: int,
    fallback_name: str,
    tracked_handles: Optional[set[str]],
    session: requests.Session,
    user_cache: dict[str, str],
    contest_cache: dict[int, str],
) -> int:
    """Fetch standings for one contest and upsert data.

    When *tracked_handles* is a set, only rows belonging to those handles
    are upserted.  When it is ``None``, every participant in the standings
    is treated as a tracked user.

    Returns the number of problem_result rows upserted.
    """
    cf_data = fetch_contest_standings(contest_id, session)
    if cf_data is None:
        return 0

    contest_info = cf_data.get("contest")
    problems = cf_data.get("problems", [])
    all_rows = cf_data.get("rows", [])

    if not contest_info:
        logger.warning(
            "Contest %d: standings response missing 'contest' key",
            contest_id,
        )
        return 0

    # ── upsert the contest ──────────────────────────────────────────
    contest_name = contest_info.get("name", fallback_name)
    contest_uuid = upsert_contest(
        supabase,
        cf_contest_id=contest_id,
        name=contest_name,
        start_time_seconds=contest_info.get("startTimeSeconds", 0),
        duration_seconds=contest_info.get("durationSeconds", 0),
    )
    if contest_uuid:
        contest_cache[contest_id] = contest_uuid
    else:
        logger.warning(
            "Contest %d: contest upsert failed, skipping", contest_id
        )
        return 0

    # ── process standings rows (filter to tracked handles) ──────────
    pr_rows: list[dict] = []
    matched_handles: set[str] = set()

    for row in all_rows:
        party = row.get("party", {})
        members = party.get("members", [])
        if not members:
            continue

        handle = members[0].get("handle", "").lower()
        if not handle:
            continue
        if tracked_handles is not None and handle not in tracked_handles:
            continue

        matched_handles.add(handle)

        # Ensure the user row exists.
        user_uuid = user_cache.get(handle)
        if user_uuid is None:
            # Preserve original casing for display_name.
            display_name = members[0].get("handle")
            user_uuid = upsert_user(supabase, handle, display_name)
            if user_uuid:
                user_cache[handle] = user_uuid
            else:
                logger.warning(
                    "Contest %d: could not upsert user %s, skipping",
                    contest_id,
                    handle,
                )
                continue

        problem_results = row.get("problemResults", [])

        for i, pr in enumerate(problem_results):
            if i >= len(problems):
                logger.warning(
                    "Contest %d, user %s: problemResults[%d] has no "
                    "matching problem in the problems array",
                    contest_id,
                    handle,
                    i,
                )
                continue

            problem = problems[i]
            points = float(pr.get("points", 0))
            solved = points > 0

            pr_rows.append(
                {
                    "user_id": user_uuid,
                    "contest_id": contest_uuid,
                    "problem_index": problem.get("index"),
                    "problem_rating": problem.get("rating"),
                    "verdict": "OK" if solved else None,
                    "wrong_submissions": pr.get("rejectedAttemptCount", 0),
                    "solved": solved,
                }
            )

    # ── batch upsert ────────────────────────────────────────────────
    count = upsert_problem_results_batch(supabase, pr_rows)
    if tracked_handles is not None:
        logger.info(
            "Contest %d (%s): %d total rows, %d tracked user(s) matched, "
            "%d problem_results upserted",
            contest_id,
            contest_name,
            len(all_rows),
            len(matched_handles),
            count,
        )
    else:
        logger.info(
            "Contest %d (%s): %d participants, %d problem_results upserted",
            contest_id,
            contest_name,
            len(all_rows),
            count,
        )
    return count


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full fetch-and-upsert pipeline.

    Two independent paths feed the same tables:

    1. **handles.txt** — discover contests from tracked users' rating
       history, then fetch standings filtered to those handles.
    2. **contests.txt** — fetch full standings for fixed contest IDs,
       treating every participant as a tracked user.

    Each path writes its own ``fetch_log`` row (keyed by ``source``) so
    you can tell which one contributed what.
    """
    logger.info("=" * 60)
    logger.info("cf-leaderboard fetcher starting")

    config = load_config()
    supabase = init_supabase(
        config["SUPABASE_URL"], config["SUPABASE_SERVICE_KEY"]
    )

    session = requests.Session()
    session.headers["User-Agent"] = "cf-leaderboard-fetcher/1.0"

    user_cache, contest_cache = preload_caches(supabase)

    # ── load inputs ──────────────────────────────────────────────────
    handles = load_handles(
        Path(__file__).resolve().parent / "handles.txt"
    )
    logger.info(
        "Loaded %d handle(s): %s", len(handles), ", ".join(handles)
    )

    contest_ids = load_contest_ids(
        Path(__file__).resolve().parent / "contests.txt"
    )
    if contest_ids:
        logger.info(
            "Loaded %d contest ID(s): %s",
            len(contest_ids),
            ", ".join(str(c) for c in contest_ids),
        )

    # ── handles.txt path ─────────────────────────────────────────────
    h_contests = 0
    h_pr_rows = 0
    h_error: Optional[str] = None
    tracked_handles: set[str] = set(handles)

    if handles:
        try:
            contests = collect_contest_ids(handles, session)
            # Drop contests we've already processed so we don't re-fetch
            # standings for them on every run.
            new_contests = {
                cid: cname
                for cid, cname in contests.items()
                if cid not in contest_cache
            }
            skipped = len(contests) - len(new_contests)
            if skipped:
                logger.info(
                    "[handles.txt] Skipping %d already-processed contest(s)",
                    skipped,
                )
            logger.info(
                "[handles.txt] %d new contest(s) to process (of %d total)",
                len(new_contests),
                len(contests),
            )
            for cid, cname in new_contests.items():
                count = process_contest_standings(
                    supabase,
                    cid,
                    cname,
                    tracked_handles,
                    session,
                    user_cache,
                    contest_cache,
                )
                h_pr_rows += count
                h_contests += 1
        except Exception as exc:
            logger.exception(
                "[handles.txt] Unhandled exception during fetch"
            )
            h_error = (
                f"{exc.__class__.__name__}: {exc}\n"
                f"{traceback.format_exc()}"
            )

        h_status = "error" if h_error else "success"
        try:
            write_fetch_log(
                supabase,
                h_status,
                h_contests,
                h_error,
                source="handles.txt",
            )
        except Exception:
            logger.exception(
                "Failed to write fetch_log for handles.txt"
            )

    # ── contests.txt path ────────────────────────────────────────────
    c_contests = 0
    c_pr_rows = 0
    c_error: Optional[str] = None

    if contest_ids:
        try:
            for cid in contest_ids:
                count = process_contest_standings(
                    supabase,
                    cid,
                    "",  # fallback_name — standings response provides the real name
                    None,  # tracked_handles=None → ALL participants
                    session,
                    user_cache,
                    contest_cache,
                )
                c_pr_rows += count
                c_contests += 1
        except Exception as exc:
            logger.exception(
                "[contests.txt] Unhandled exception during fetch"
            )
            c_error = (
                f"{exc.__class__.__name__}: {exc}\n"
                f"{traceback.format_exc()}"
            )

        c_status = "error" if c_error else "success"
        try:
            write_fetch_log(
                supabase,
                c_status,
                c_contests,
                c_error,
                source="contests.txt",
            )
        except Exception:
            logger.exception(
                "Failed to write fetch_log for contests.txt"
            )

    # ── scoring ──────────────────────────────────────────────────────
    scored = 0
    try:
        scored = compute_and_update_scores(supabase)
    except Exception:
        logger.exception("Scoring step failed")

    # ── summary ──────────────────────────────────────────────────────
    total_contests = h_contests + c_contests
    total_pr_rows = h_pr_rows + c_pr_rows
    overall = (
        "error"
        if (h_error or c_error)
        else "success"
    )

    logger.info(
        "Fetch complete: status=%s, contests_processed=%d "
        "(handles.txt=%d, contests.txt=%d), "
        "problem_results_upserted=%d (handles.txt=%d, contests.txt=%d), "
        "rows_scored=%d",
        overall,
        total_contests,
        h_contests,
        c_contests,
        total_pr_rows,
        h_pr_rows,
        c_pr_rows,
        scored,
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
