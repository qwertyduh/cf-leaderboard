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


def test_base_points_full_table() -> None:
    """Every set/slot pair matches the §4.1 table."""
    expected = {
        "A": {1: 100, 2: 100, 3: 125, 4: 125, 5: 150, 6: 150, 7: 200, 8: 200},
        "B": {1: 200, 2: 200, 3: 250, 4: 250, 5: 300, 6: 300, 7: 400, 8: 400},
        "C": {1: 300, 2: 300, 3: 375, 4: 375, 5: 450, 6: 450, 7: 600, 8: 600},
    }
    for set_name, slots in expected.items():
        for slot, pts in slots.items():
            assert base_points(set_name, slot) == pts, (set_name, slot)


def test_set_totals_match_doc() -> None:
    """Set totals: A=1150, B=2300, C=3450; max attainable base = 6900 (§4.1)."""
    totals = {
        s: sum(base_points(s, slot) for slot in range(1, 9))
        for s in ("A", "B", "C")
    }
    assert totals == {"A": 1150, "B": 2300, "C": 3450}
    assert sum(totals.values()) == 6900


def test_base_points_case_insensitive() -> None:
    assert base_points("a", 1) == 100
    assert base_points("c", 8) == 600


def test_base_points_fallback_when_untagged() -> None:
    assert base_points(None, None) == DEFAULT_BASE
    assert base_points("A", None) == DEFAULT_BASE
    assert base_points("Z", 3) == DEFAULT_BASE
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


def test_worked_example_c5() -> None:
    """Doc §4.4: 450 * 0.70 * 1.12 = 352.8."""
    score = compute_score(
        set_name="C",
        slot=5,
        solve_order=2,
        wrong_submissions=2,
        solved=True,
    )
    assert round(score, 4) == 352.8


# -------------------------------------------------------------------
# compute_score composition + edge cases
# -------------------------------------------------------------------


def test_clean_first_solve() -> None:
    """A1 first solver, no wrongs: 100 * 1.0 * 1.20 = 120."""
    assert compute_score("A", 1, 1, 0, True) == 120.0


def test_unsolved_is_zero() -> None:
    assert compute_score("C", 8, 1, 0, False) == 0.0


def test_solve_outside_top3_no_bonus() -> None:
    """B7 (400), 4th solver, 1 wrong: 400 * 0.85 * 1.0 = 340."""
    assert compute_score("B", 7, 4, 1, True) == 340.0


def test_full_precision_not_rounded() -> None:
    """Scores keep full precision; rounding is a display concern only."""
    # A3 (125) * decay(1)=0.85 * 1st=1.20 = 127.5
    assert compute_score("A", 3, 1, 1, True) == 127.5


# -------------------------------------------------------------------
# constants sanity
# -------------------------------------------------------------------


def test_constants_sane() -> None:
    assert 0.0 < WRONG_FLOOR < 1.0
    assert DEFAULT_BASE > 0
    assert all(m > 1.0 for m in FIRST_SOLVER_MULTIPLIERS.values())
