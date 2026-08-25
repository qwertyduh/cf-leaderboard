"""Probe ``contest.standings`` for a mashup — unsigned vs signed.

Standalone live test.  Hits the Codeforces API for the contest in
``contests.txt`` (or one passed via ``--contest``) twice:

  * **unsigned** — the plain public URL (should FAIL for a mashup), and
  * **signed**  — built via :func:`cf_auth.build_signed_url`
    (should return standings, provided the account owning the key is a
    participant/coach/manager of the mashup — see note in ``cf_auth.py``).

Usage::

    cd fetcher
    python check_mashup_auth.py                    # first ID in contests.txt
    python check_mashup_auth.py --contest 1234     # explicit contest ID
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from cf_auth import CF_API_BASE, build_signed_url


def load_cf_credentials() -> tuple[str, str]:
    """Read CF_API_KEY / CF_API_SECRET from .env in the project root."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    return os.environ.get("CF_API_KEY", ""), os.environ.get("CF_API_SECRET", "")


def first_contest_id() -> Optional[int]:
    """Return the first valid contest ID in ``contests.txt`` (or None)."""
    path = Path(__file__).resolve().parent / "contests.txt"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            return int(stripped)
        except ValueError:
            continue
    return None


def probe(url: str, label: str) -> None:
    """GET *url* and print a one-line status/comment summary."""
    resp = requests.get(url, timeout=30)
    try:
        data = resp.json()
    except ValueError:
        print(f"[{label}] non-JSON response (HTTP {resp.status_code})")
        return

    if data.get("status") == "OK":
        result = data.get("result", {})
        rows = result.get("rows", []) if isinstance(result, dict) else None
        n = len(rows) if rows is not None else "?"
        print(f"[{label}] status=OK  rows={n}")
    else:
        print(
            f"[{label}] status=FAILED  comment={data.get('comment', 'no comment')!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contest",
        type=int,
        default=None,
        help="contest ID to probe (default: first ID in contests.txt)",
    )
    args = parser.parse_args()

    contest_id = args.contest if args.contest is not None else first_contest_id()
    if contest_id is None:
        print(
            "No contest ID found. Add the mashup ID to fetcher/contests.txt "
            "or pass --contest <id>."
        )
        sys.exit(1)

    api_key, api_secret = load_cf_credentials()
    if not api_key or not api_secret:
        print(
            "CF_API_KEY / CF_API_SECRET not set in .env — cannot build a "
            "signed request."
        )
        sys.exit(1)

    unsigned = f"{CF_API_BASE}/contest.standings?contestId={contest_id}"
    signed = build_signed_url(
        "contest.standings", {"contestId": contest_id}, api_key, api_secret
    )

    print(f"Probing contest.standings for contest {contest_id}\n")
    probe(unsigned, "unsigned")
    probe(signed, "signed")
    print(
        "\nIf unsigned=FAILED and signed=OK, mashup signing is working.\n"
        "If signed=FAILED too, check that the CF account owning the key "
        "participates in / manages this mashup (see cf_auth.py)."
    )


if __name__ == "__main__":
    main()
