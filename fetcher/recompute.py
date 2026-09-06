#!/usr/bin/env python
"""Manual recompute / CSV fallback - the §5.3 override path.

Two modes:

* ``--all`` (default): recompute **every** contest's ``problem_results`` from
  the submissions already stored in Supabase, then refresh the leaderboard
  snapshot.  Use this after changing the scoring constants in ``scoring.py`` or
  whenever you need a deterministic, from-scratch re-score (§13).

* ``--csv PATH``: load a CSV submission dump into the ``submissions`` table
  first, then run the same full recompute.  This is the mandatory fallback for
  when the live CF API path is unavailable mid-contest (§5.3) - it must be
  usable within ten minutes, so keep a fresh dump handy.

CSV format (header row required)::

    submission_id,handle,cf_contest_id,problem_index,verdict,creation_time_seconds
    331084,qwertyduh,709198,A,OK,1725100000
    331085,debug_addict,709198,A,WRONG_ANSWER,1725100050

``verdict`` uses Codeforces spelling (``OK``, ``WRONG_ANSWER``,
``COMPILATION_ERROR``, …); compile errors are ignored by the scorer (§4.2).

Usage::

    cd fetcher && source .venv/bin/activate
    python recompute.py                     # full recompute from stored subs
    python recompute.py --csv dump.csv      # import a dump, then recompute
"""

import argparse
import csv
import sys
from pathlib import Path

from main import (
    init_supabase,
    load_config,
    preload_caches,
    preload_problem_catalog,
    recompute_all,
    upsert_contest,
    upsert_submissions_batch,
    upsert_user,
    write_leaderboard_snapshot,
)

REQUIRED_COLUMNS = {
    "submission_id",
    "handle",
    "cf_contest_id",
    "problem_index",
    "verdict",
    "creation_time_seconds",
}


def import_csv(supabase, path: Path) -> int:
    """Load a CSV submission dump into the ``submissions`` table.

    Upserts users and (minimally) contests as needed so foreign keys resolve,
    then batch-upserts the submissions (deduped on CF submission id).
    Returns the number of submission rows upserted.
    """
    user_cache, contest_cache = preload_caches(supabase)

    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(
                f"CSV is missing required column(s): {', '.join(sorted(missing))}"
            )

        rows: list[dict] = []
        skipped = 0
        for line in reader:
            try:
                sub_id = int(line["submission_id"])
                cf_contest_id = int(line["cf_contest_id"])
                ct = int(line["creation_time_seconds"])
            except (ValueError, KeyError):
                skipped += 1
                continue

            handle = (line["handle"] or "").strip().lower()
            problem_index = (line["problem_index"] or "").strip()
            verdict = (line["verdict"] or "").strip() or None
            if not handle or not problem_index:
                skipped += 1
                continue

            # Resolve user.
            user_uuid = user_cache.get(handle)
            if user_uuid is None:
                user_uuid = upsert_user(supabase, handle, line["handle"].strip())
                if user_uuid:
                    user_cache[handle] = user_uuid
                else:
                    skipped += 1
                    continue

            # Resolve contest - create a minimal row only if we've never seen it
            # (never clobber real metadata pulled from the API).
            contest_uuid = contest_cache.get(cf_contest_id)
            if contest_uuid is None:
                contest_uuid = upsert_contest(
                    supabase,
                    cf_contest_id=cf_contest_id,
                    name=f"CSV import {cf_contest_id}",
                    start_time_seconds=0,
                    duration_seconds=0,
                )
                if contest_uuid:
                    contest_cache[cf_contest_id] = contest_uuid
                else:
                    skipped += 1
                    continue

            rows.append(
                {
                    "id": sub_id,
                    "user_id": user_uuid,
                    "contest_id": contest_uuid,
                    "problem_index": problem_index,
                    "verdict": verdict,
                    "creation_time_seconds": ct,
                }
            )

    imported = 0
    # Upsert in chunks to keep request sizes sane.
    for i in range(0, len(rows), 500):
        imported += upsert_submissions_batch(supabase, rows[i : i + 500])

    print(f"Imported {imported} submission(s) from {path} ({skipped} skipped).")
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="CSV submission dump to import before recomputing",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Recompute all contests from stored submissions (the default)",
    )
    args = parser.parse_args()

    config = load_config()
    supabase = init_supabase(
        config["SUPABASE_URL"], config["SUPABASE_SERVICE_KEY"]
    )

    if args.csv:
        if not args.csv.exists():
            print(f"CSV not found: {args.csv}")
            sys.exit(1)
        import_csv(supabase, args.csv)

    catalog = preload_problem_catalog(supabase)
    updated = recompute_all(supabase, catalog)
    snapshot = write_leaderboard_snapshot(supabase)
    print(
        f"Recompute complete: {updated} problem_results updated, "
        f"{snapshot} snapshot row(s) written."
    )


if __name__ == "__main__":
    main()
