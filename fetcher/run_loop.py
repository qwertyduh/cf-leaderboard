"""Continuous fetcher loop — re-runs main.py on a fixed interval.

Start this inside ``screen`` so it survives terminal close::

    screen -S cf-fetch
    source .venv/bin/activate && python run_loop.py

Detach with ``Ctrl-a d``.  Reattach later with ``screen -r cf-fetch``.
"""

import logging
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

POLL_MINUTES = 15
RUN_TIMEOUT_SECONDS = 14 * 60  # kill if a single run exceeds this
FETCHER_DIR = Path(__file__).resolve().parent
MAIN_SCRIPT = FETCHER_DIR / "main.py"
LOG_FILE = FETCHER_DIR / "run_loop.log"

# ---------------------------------------------------------------------------
# logging — writes to both console and file
# ---------------------------------------------------------------------------


def setup_logging() -> logging.Logger:
    _logger = logging.getLogger("cf-runner")
    _logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console — INFO and above
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    _logger.addHandler(console)

    # File — DEBUG and above (everything)
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    _logger.addHandler(file_handler)

    return _logger


logger = setup_logging()

# ---------------------------------------------------------------------------
# main loop
# ---------------------------------------------------------------------------


def tail(lines: str, n: int = 15) -> str:
    """Return the last *n* non-empty lines of *lines*."""
    return "\n".join(
        [l for l in lines.strip().splitlines() if l][-n:]
    )


def run_once() -> int:
    """Launch ``main.py`` as a subprocess.

    Returns the process exit code.  A non-zero exit code means the run
    itself signalled an error (the fetcher top-level exception handler
    already logged the details and wrote a fetch_log row).
    """
    start = time.monotonic()
    logger.info("─" * 50)
    logger.info("Starting fetch run")
    try:
        result = subprocess.run(
            [sys.executable, str(MAIN_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            cwd=str(FETCHER_DIR),
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        logger.error(
            "Run timed out after %.0f s (limit=%d s)",
            elapsed,
            RUN_TIMEOUT_SECONDS,
        )
        return -1

    elapsed = time.monotonic() - start
    logger.info(
        "Run finished in %.0f s — exit code %d", elapsed, result.returncode
    )

    # Show the last few lines of the fetcher's own log output.
    if result.stdout:
        for line in tail(result.stdout, n=8).splitlines():
            logger.info("[fetcher] %s", line)

    if result.returncode != 0 and result.stderr:
        for line in tail(result.stderr, n=10).splitlines():
            logger.warning("[fetcher stderr] %s", line)

    return result.returncode


def main() -> None:
    logger.info(
        "cf-leaderboard loop starting — poll every %d min, timeout=%d s",
        POLL_MINUTES,
        RUN_TIMEOUT_SECONDS,
    )

    run_count = 0
    failures = 0

    while True:
        run_count += 1
        next_run = (
            datetime.now(tz=timezone.utc).isoformat()
        )
        logger.info(
            "Run #%d (%d failures so far) — next poll at %s",
            run_count,
            failures,
            next_run,
        )

        try:
            rc = run_once()
            if rc != 0:
                failures += 1
        except Exception:
            logger.exception(
                "Unhandled exception in run_loop itself — continuing loop"
            )
            failures += 1

        logger.info(
            "Sleeping %d min until next run …", POLL_MINUTES
        )
        time.sleep(POLL_MINUTES * 60)


if __name__ == "__main__":
    main()
