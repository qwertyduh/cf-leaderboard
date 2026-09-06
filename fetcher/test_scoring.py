"""Unit tests for :mod:`scoring` - the §4 contest scoring model."""

from scoring import (
    DEFAULT_BASE,
    FIRST_SOLVER_MULTIPLIERS,
    WRONG_FLOOR,
    base_points,
    compute_score,
    decay,
    first_solver_multiplier,
)


# -------------------------------------------------------------------
# §4.1 base points by (set, slot)
# -------------------------------------------------------------------


def test_base_points_per_slot() -> None:
    """Base rises 10 per slot: slots 1..8 -> 100, 110, ... 170 (§4.1)."""
    expected = {1: 100, 2: 110, 3: 120, 4: 130, 5: 140, 6: 150, 7: 160, 8: 170}
    for slot, pts in expected.items():
        assert base_points("A", slot) == pts, slot


def test_base_points_set_independent() -> None:
    """Set no longer affects the base; a given slot scores the same everywhere."""
    for slot in range(1, 9):
        assert base_points("A", slot) == base_points("B", slot) == base_points("C", slot)
    # A later problem always outscores an earlier one.
    assert base_points("A", 4) > base_points("C", 1)


def test_base_points_fallback_when_untagged() -> None:
    assert base_points(None, None) == DEFAULT_BASE
    assert base_points("A", None) == DEFAULT_BASE
    assert base_points("A", 9) == DEFAULT_BASE
    assert base_points("A", 0) == DEFAULT_BASE


# -------------------------------------------------------------------
# §4.2 wrong-answer decay: max(0.4, 1 - 0.15 * W)
# -------------------------------------------------------------------


def test_decay_table() -> None:
    """Doc §4.2 multiplier table: 1.00 / 0.85 / 0.70 / 0.55 / 0.40."""
    assert decay(0) == 1.00
    assert decay(1) == 0.85
    assert decay(2) == 0.70
    assert decay(3) == 0.55
    assert decay(4) == 0.40


def test_decay_floors_at_0_4() -> None:
    """5+ wrong submissions never drop below the 0.4 floor."""
    assert decay(5) == WRONG_FLOOR
    assert decay(10) == WRONG_FLOOR
    assert WRONG_FLOOR == 0.40


# -------------------------------------------------------------------
# §4.3 first-solver multiplier
# -------------------------------------------------------------------


def test_first_solver_multipliers() -> None:
    assert first_solver_multiplier(1) == 1.20
    assert first_solver_multiplier(2) == 1.12
    assert first_solver_multiplier(3) == 1.06
    assert first_solver_multiplier(4) == 1.00
    assert first_solver_multiplier(None) == 1.00
    assert FIRST_SOLVER_MULTIPLIERS == {1: 1.20, 2: 1.12, 3: 1.06}


# -------------------------------------------------------------------
# §4.4 worked example: C5, 2 prior wrong, 2nd solver -> 352.8
# -------------------------------------------------------------------


def test_worked_example_slot5() -> None:
    """Doc §4.4: slot 5 base 140, 2 wrong, 2nd solver -> 140 * 0.70 * 1.12 = 109.76."""
    score = compute_score(
        set_name="C",
        slot=5,
        solve_order=2,
        wrong_submissions=2,
        solved=True,
    )
    assert round(score, 4) == 109.76


# -------------------------------------------------------------------
# compute_score composition + edge cases
# -------------------------------------------------------------------


def test_clean_first_solve() -> None:
    """A1 first solver, no wrongs: 100 * 1.0 * 1.20 = 120."""
    assert compute_score("A", 1, 1, 0, True) == 120.0


def test_unsolved_is_zero() -> None:
    assert compute_score("C", 8, 1, 0, False) == 0.0


def test_solve_outside_top3_no_bonus() -> None:
    """Slot 7 base 160, 4th solver, 1 wrong: 160 * 0.85 * 1.0 = 136."""
    assert compute_score("B", 7, 4, 1, True) == 136.0


def test_full_precision_not_rounded() -> None:
    """Scores keep full precision; rounding is a display concern only."""
    # slot 3 base 120 * decay(1)=0.85 * 1st=1.20 = 122.4
    assert round(compute_score("A", 3, 1, 1, True), 4) == 122.4


# -------------------------------------------------------------------
# constants sanity
# -------------------------------------------------------------------


def test_constants_sane() -> None:
    assert 0.0 < WRONG_FLOOR < 1.0
    assert DEFAULT_BASE > 0
    assert all(m > 1.0 for m in FIRST_SOLVER_MULTIPLIERS.values())
