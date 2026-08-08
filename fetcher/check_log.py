#!/usr/bin/env python
"""Print the last few fetch_log rows — no SQL required.

Usage::

    source .venv/bin/activate && python check_log.py

To watch continuously (Ctrl-C to stop)::

    source .venv/bin/activate && python check_log.py --watch
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


def main() -> None:
    parser = argparse.ArgumentParser(description="Check cf-leaderboard fetch_log")
    parser.add_argument(
        "-n", "--limit", type=int, default=10, help="Rows to show (default: 10)"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Refresh every 30 s (Ctrl-C to stop)",
    )
    args = parser.parse_args()

    # Load config from the same .env as main.py.
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        print("❌  Missing SUPABASE_URL or SUPABASE_SECRET_KEY in .env")
        sys.exit(1)

    supabase = create_client(url, key)

    while True:
        try:
            resp = (
                supabase.table("fetch_log")
                .select("id,run_at,status,source,contests_processed,error")
                .order("run_at", desc=True)
                .limit(args.limit)
                .execute()
            )
            rows = resp.data or []

            print()
            print(
                f"{'run_at':<20}  {'status':<8}  {'source':<14}  "
                f"{'contests':>8}"
            )
            print("-" * 62)
            for row in rows:
                ts = (
                    row["run_at"][:19].replace("T", " ")
                    if row.get("run_at")
                    else "-"
                )
                status = row.get("status", "?")
                source = row.get("source") or "-"
                contests = row.get("contests_processed", 0)
                err = row.get("error")
                line = (
                    f"{ts:<20}  {status:<8}  {source:<14}  "
                    f"{contests:>8}"
                )
                if status == "error":
                    line += "  ⚠️"
                else:
                    line += "  ✅"
                if err:
                    # Show first line of error.
                    first_line = err.split("\n")[0][:60]
                    line += f"  {first_line}"
                print(line)
            print(f"\n({len(rows)} row(s), {datetime.now():%H:%M:%S})")
        except Exception as exc:
            msg = str(exc)
            if "PGRST205" in msg or "Could not find the table" in msg:
                print(
                    "❌  Tables don't exist yet.\n\n"
                    "    Run the four SQL files from supabase/ in the Supabase SQL Editor:\n"
                    "    https://supabase.com/dashboard/project/wrdwuzmjzcscolhjejtk/sql\n\n"
                    "    Order: 001_tables.sql → 002_rls.sql → 003_view.sql → 004_fetch_log_source.sql"
                )
            else:
                print(f"❌  Query failed: {exc}")

        if not args.watch:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
