"""Unit tests for :mod:`scoring`."""

import pytest
from scoring import (
    BASE_SCORE,
    DEFAULT_DIFFICULTY,
    PENALTY_FLOOR,
    PENALTY_PER_WRONG,
    TOP3_MULTIPLIER,
    compute_score,
)


# -------------------------------------------------------------------
# clean top-3 solve with no wrong submissions
# -------------------------------------------------------------------


def test_top3_clean_solve() -> None:
    """A first-solver with a 2000-rated problem and zero wrong tries."""
    score = compute_score(
        problem_rating=2000,
        solve_order=1,
        wrong_submissions=0,
        solved=True,
    )
    # difficulty = 2000/1000 = 2.0
    # top3 = 1.5, penalty = 1.0
    expected = BASE_SCORE * 2.0 * TOP3_MULTIPLIER * 1.0
    assert score == expected


# -------------------------------------------------------------------
# solve with several wrong submissions — penalty should floor at 0.6
# -------------------------------------------------------------------


def test_penalty_floors_at_0_6() -> None:
    """10 wrong submissions → penalty would be 0.0 but floors at 0.6."""
    score = compute_score(
        problem_rating=1000,
        solve_order=None,
        wrong_submissions=10,
        solved=True,
    )
    # difficulty = 1.0, top3 = 1.0, penalty = max(0.6, 1 - 0.1*10) = max(0.6, 0.0) = 0.6
    expected = BASE_SCORE * 1.0 * 1.0 * PENALTY_FLOOR
    assert score == expected


def test_penalty_just_above_floor() -> None:
    """3 wrong submissions → penalty = 0.7 (still above the 0.6 floor)."""
    score = compute_score(
        problem_rating=1000,
        solve_order=None,
        wrong_submissions=3,
        solved=True,
    )
    # penalty = max(0.6, 1 - 0.3) = 0.7
    expected = BASE_SCORE * 1.0 * 1.0 * 0.7
    assert score == expected


def test_penalty_exactly_at_floor() -> None:
    """4 wrong submissions → penalty = 0.6 exactly."""
    score = compute_score(
        problem_rating=1000,
        solve_order=None,
        wrong_submissions=4,
        solved=True,
    )
    # penalty = max(0.6, 1 - 0.4) = 0.6
    expected = BASE_SCORE * 1.0 * 1.0 * PENALTY_FLOOR
    assert score == expected


# -------------------------------------------------------------------
# unsolved → score must be 0
# -------------------------------------------------------------------


def test_unsolved_zero_score() -> None:
    """An unsolved problem yields 0 regardless of other fields."""
    score = compute_score(
        problem_rating=3000,
        solve_order=1,
        wrong_submissions=0,
        solved=False,
    )
    assert score == 0.0


# -------------------------------------------------------------------
# solve outside top 3 (no multiplier)
# -------------------------------------------------------------------


def test_outside_top3() -> None:
    """solve_order=None → top3_multiplier is 1.0."""
    score = compute_score(
        problem_rating=1500,
        solve_order=None,
        wrong_submissions=1,
        solved=True,
    )
    # difficulty = 1.5, top3 = 1.0, penalty = max(0.6, 0.9) = 0.9
    expected = BASE_SCORE * 1.5 * 1.0 * 0.9
    assert score == expected


def test_solve_order_4_no_bonus() -> None:
    """solve_order=4 → no top-3 bonus."""
    score = compute_score(
        problem_rating=1500,
        solve_order=4,
        wrong_submissions=0,
        solved=True,
    )
    expected = BASE_SCORE * 1.5 * 1.0 * 1.0
    assert score == expected


# -------------------------------------------------------------------
# missing problem_rating → uses DEFAULT_DIFFICULTY
# -------------------------------------------------------------------


def test_missing_rating() -> None:
    """When problem_rating is None, default difficulty is used."""
    score = compute_score(
        problem_rating=None,
        solve_order=None,
        wrong_submissions=0,
        solved=True,
    )
    expected = BASE_SCORE * DEFAULT_DIFFICULTY * 1.0 * 1.0
    assert score == expected


# -------------------------------------------------------------------
# constants sanity checks
# -------------------------------------------------------------------


def test_constants_are_positive() -> None:
    """All tunable constants should be positive numbers."""
    assert BASE_SCORE > 0
    assert TOP3_MULTIPLIER > 1.0
    assert 0.0 < PENALTY_FLOOR < 1.0
    assert PENALTY_PER_WRONG > 0
    assert DEFAULT_DIFFICULTY > 0
