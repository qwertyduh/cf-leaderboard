"""Pure scoring function for cf-leaderboard — no DB or API dependencies.

Import this from ``main.py`` (or anywhere else) and call :func:`compute_score`
with the raw column values from a ``problem_results`` row.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# tunable constants
# ---------------------------------------------------------------------------

BASE_SCORE = 100          # base points for any solved problem
TOP3_MULTIPLIER = 1.5     # bonus for first, second, or third solver
PENALTY_FLOOR = 0.6       # penalty_factor cannot drop below this
PENALTY_PER_WRONG = 0.1   # penalty applied per wrong submission
DEFAULT_DIFFICULTY = 1.0  # used when problem_rating is missing (None)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def compute_score(
    problem_rating: Optional[int],
    solve_order: Optional[int],
    wrong_submissions: int,
    solved: bool,
) -> float:
    """Return the score for a single problem result.

    Parameters
    ----------
    problem_rating:
        CF problem rating (e.g. 800–3500).  When ``None`` the
        *difficulty_factor* defaults to :data:`DEFAULT_DIFFICULTY`.
    solve_order:
        ``1``, ``2``, or ``3`` for the first three solvers; ``None``
        (or any value >3) means no top-3 bonus.
    wrong_submissions:
        Number of rejected attempts before the first accepted solution.
    solved:
        Whether the problem was ultimately accepted.

    Returns
    -------
    float
        The computed score, always ≥ 0.  An unsolved problem yields 0
        regardless of other inputs.
    """
    if not solved:
        return 0.0

    difficulty_factor = (
        problem_rating / 1000.0
        if problem_rating is not None
        else DEFAULT_DIFFICULTY
    )

    top3_multiplier = (
        TOP3_MULTIPLIER
        if solve_order is not None and 1 <= solve_order <= 3
        else 1.0
    )

    penalty_factor = max(
        PENALTY_FLOOR, 1.0 - PENALTY_PER_WRONG * wrong_submissions
    )

    return BASE_SCORE * difficulty_factor * top3_multiplier * penalty_factor * 1.0
