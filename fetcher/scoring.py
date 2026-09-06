"""Pure scoring function for cf-leaderboard - no DB or API dependencies.

Implements the scoring model from §4 of the contest documentation:

* **Base points** depend on the problem's *set* (A / B / C) and its *slot*
  (1–8 within that set), per the §4.1 table - NOT on the Codeforces problem
  rating.  A problem's ``(set, slot)`` tag lives in the ``problems`` table and
  is seeded by organizers.
* **Wrong-answer decay** (§4.2): ``decay(W) = max(0.4, 1 - 0.15 * W)``.
  Compilation errors are excluded upstream (the caller passes a
  ``wrong_submissions`` count that already omits CEs - see
  ``fetcher/main.py``).
* **First-solver multiplier** (§4.3): 1.20 / 1.12 / 1.06 for the 1st / 2nd /
  3rd solver of a problem; 1.00 for everyone else.

Import this from ``main.py`` (or anywhere else) and call :func:`compute_score`.
Scores are returned at full precision; rounding to the nearest integer happens
only at *display* time (§4.4), never here.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# tunable constants (§4)
# ---------------------------------------------------------------------------

# §4.1 base-points table.  Each set maps to four difficulty tiers covering
# slot pairs (1-2), (3-4), (5-6), (7-8).
_SET_BASE_TIERS: dict[str, tuple[int, int, int, int]] = {
    "A": (100, 125, 150, 200),
    "B": (200, 250, 300, 400),
    "C": (300, 375, 450, 600),
}

DEFAULT_BASE = 100  # fallback base when a problem has no (set, slot) tag yet

# §4.2 wrong-answer decay.
WRONG_FLOOR = 0.40       # decay cannot drop below this
WRONG_PER_SUBMISSION = 0.15  # each wrong (non-CE) submission costs this much

# §4.3 first-solver multipliers, keyed by solve order (1st / 2nd / 3rd).
FIRST_SOLVER_MULTIPLIERS: dict[int, float] = {1: 1.20, 2: 1.12, 3: 1.06}


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def base_points(set_name: Optional[str], slot: Optional[int]) -> int:
    """Return the §4.1 base points for a problem's ``(set, slot)``.

    Falls back to :data:`DEFAULT_BASE` when the set is unknown or the slot is
    out of the 1–8 range (e.g. a problem that organizers have not tagged in the
    ``problems`` table yet).
    """
    tiers = _SET_BASE_TIERS.get((set_name or "").strip().upper())
    if tiers is None or slot is None or slot < 1 or slot > 8:
        return DEFAULT_BASE
    return tiers[(slot - 1) // 2]


def decay(wrong_submissions: int) -> float:
    """Return the §4.2 wrong-answer decay multiplier for *wrong_submissions*."""
    if wrong_submissions <= 0:
        return 1.0
    return max(WRONG_FLOOR, 1.0 - WRONG_PER_SUBMISSION * wrong_submissions)


def first_solver_multiplier(solve_order: Optional[int]) -> float:
    """Return the §4.3 multiplier for a given solve order (1.00 outside top 3)."""
    if solve_order is None:
        return 1.0
    return FIRST_SOLVER_MULTIPLIERS.get(solve_order, 1.0)


def compute_score(
    set_name: Optional[str],
    slot: Optional[int],
    solve_order: Optional[int],
    wrong_submissions: int,
    solved: bool,
) -> float:
    """Return the score for a single problem result (§4.4).

    Parameters
    ----------
    set_name:
        The problem's set - ``'A'``, ``'B'`` or ``'C'``.  ``None`` (untagged)
        falls back to :data:`DEFAULT_BASE`.
    slot:
        The problem's slot within its set (1–8, easiest to hardest).  ``None``
        falls back to :data:`DEFAULT_BASE`.
    solve_order:
        ``1``, ``2`` or ``3`` for the first three solvers; ``None`` (or any
        value > 3) means no first-solver bonus.
    wrong_submissions:
        Number of rejected, non-compilation-error attempts before the first
        accepted solution.
    solved:
        Whether the problem was ultimately accepted.

    Returns
    -------
    float
        ``base * decay(W) * first_solver_multiplier``, at full precision.
        An unsolved problem yields ``0.0`` regardless of other inputs.
    """
    if not solved:
        return 0.0

    return (
        base_points(set_name, slot)
        * decay(wrong_submissions)
        * first_solver_multiplier(solve_order)
    )
