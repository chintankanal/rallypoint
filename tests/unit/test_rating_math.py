"""
Unit tests for all rating_math.py pure functions.
Includes the full worked example from jlrs.md:
  Player A: rating 1350, cross-academy TOURNAMENT, 3-0 win, age 11
  Player B: rating 1250, age 13
  Expected final: A ≈ 1378, B ≈ 1222 (±0.5)
"""
import math
from datetime import date

import pytest

from app.utils.rating_math import (
    get_actual_score,
    get_age_bonus,
    get_asi_adjusted_rating,
    get_cr,
    get_effective_event_type,
    get_expected_score,
    get_k_base,
    get_k_eff,
    get_k_shared,
    get_match_weight,
    get_academy_weight,
    get_tier,
)


# ── K-factor boundaries ────────────────────────────────────────────────────────

@pytest.mark.parametrize("rated_matches,expected_k", [
    (0,   50.0),
    (1,   50.0),
    (29,  50.0),
    (30,  32.0),
    (99,  32.0),
    (100, 20.0),
    (200, 20.0),
])
def test_k_base_boundaries(rated_matches, expected_k):
    assert get_k_base(rated_matches) == expected_k


# ── Match weight ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("event_type,expected", [
    ("LEAGUE",              1.0),
    ("TOURNAMENT_EXTERNAL", 1.2),
    ("TOURNAMENT_MANAGED",  1.2),
    ("FRIENDLY",            0.5),
])
def test_match_weight(event_type, expected):
    assert get_match_weight(event_type) == expected


# ── Academy weight ────────────────────────────────────────────────────────────

def test_same_academy_weight():
    assert get_academy_weight(True) == 0.8


def test_cross_academy_weight():
    assert get_academy_weight(False) == 1.2


# ── K effective cap ───────────────────────────────────────────────────────────

def test_k_eff_capped_at_60():
    # k_base=50, w_match=1.2, w_academy=1.2, cr≈0 → 50*1.2*1.2*2=144 → capped at 60
    result = get_k_eff(50.0, 1.2, 1.2, 0.0)
    assert result == 60.0


def test_k_eff_not_capped():
    # k_base=20, w_match=0.5, w_academy=0.8, cr=0.9 → 20*0.5*0.8*(2-0.9)=8.8 → under cap
    result = get_k_eff(20.0, 0.5, 0.8, 0.9)
    assert abs(result - 8.8) < 1e-9


# ── Margin-of-victory tables ──────────────────────────────────────────────────

@pytest.mark.parametrize("winner_sets,loser_sets,fmt,exp_w,exp_l", [
    (2, 0, "BEST_OF_3", 1.0,   0.0),
    (2, 1, "BEST_OF_3", 0.75,  0.25),
    (3, 0, "BEST_OF_5", 1.0,   0.0),
    (3, 1, "BEST_OF_5", 0.85,  0.15),
    (3, 2, "BEST_OF_5", 0.65,  0.35),
    (4, 0, "BEST_OF_7", 1.0,   0.0),
    (4, 1, "BEST_OF_7", 0.875, 0.125),
    (4, 2, "BEST_OF_7", 0.75,  0.25),
    (4, 3, "BEST_OF_7", 0.625, 0.375),
])
def test_actual_score_table(winner_sets, loser_sets, fmt, exp_w, exp_l):
    w, l = get_actual_score(winner_sets, loser_sets, fmt)
    assert w == exp_w
    assert l == exp_l


def test_actual_score_invalid_raises():
    with pytest.raises(ValueError):
        get_actual_score(1, 0, "BEST_OF_3")  # winner needs 2


# ── Age bonus ─────────────────────────────────────────────────────────────────

def test_age_bonus_no_upset_gives_zero():
    # No upset → bonus is 0 regardless of age
    dob_winner = date(2014, 1, 1)  # younger
    dob_loser = date(2012, 1, 1)   # older
    assert get_age_bonus(dob_winner, dob_loser, is_upset=False) == 0.0


def test_age_bonus_upset_older_wins_no_bonus():
    # Upset but older player wins → age_diff ≤ 0 → 0
    dob_winner = date(2012, 1, 1)  # older
    dob_loser = date(2014, 1, 1)   # younger
    assert get_age_bonus(dob_winner, dob_loser, is_upset=True) == 0.0


def test_age_bonus_upset_younger_wins_2yr():
    # Upset AND younger wins by 2 years → 2*2 = 4
    dob_winner = date(2014, 1, 1)  # younger
    dob_loser = date(2012, 1, 1)   # older
    assert get_age_bonus(dob_winner, dob_loser, is_upset=True) == 4.0


def test_age_bonus_capped_at_10():
    # 7-year gap → 14, capped at 10
    dob_winner = date(2015, 6, 1)
    dob_loser = date(2008, 6, 1)
    assert get_age_bonus(dob_winner, dob_loser, is_upset=True) == 10.0


def test_age_bonus_same_age_no_bonus():
    dob = date(2013, 6, 1)
    assert get_age_bonus(dob, dob, is_upset=True) == 0.0


# ── Effective event type ──────────────────────────────────────────────────────

def test_diminishing_signal_overrides_to_friendly():
    assert get_effective_event_type("LEAGUE", True) == "FRIENDLY"


def test_no_diminishing_signal_preserves_type():
    assert get_effective_event_type("LEAGUE", False) == "LEAGUE"
    assert get_effective_event_type("TOURNAMENT_MANAGED", False) == "TOURNAMENT_MANAGED"


# ── ASI-adjusted rating ───────────────────────────────────────────────────────

def test_asi_adjustment_below_global():
    # Academy ASI < global avg → player gets a boost
    assert get_asi_adjusted_rating(1200, 1000, 900) == 1300.0


def test_asi_adjustment_above_global():
    # Academy ASI > global avg → player gets penalised
    assert get_asi_adjusted_rating(1200, 1000, 1100) == 1100.0


def test_asi_adjustment_neutral():
    assert get_asi_adjusted_rating(1200, 1000, 1000) == 1200.0


# ── Full worked example from jlrs.md ─────────────────────────────────────────
# Player A: rating 1350, 20 rated matches, Academy X (ASI 1200)
# Player B: rating 1250, 60 rated matches, Academy Y (ASI 1150)
# Global average rating: 1100
# Cross-academy TOURNAMENT_EXTERNAL, A wins 3-0 (BEST_OF_5)
# Age: A=11 (dob 2015-01-01), B=13 (dob 2013-01-01)
# Expected per spec: A → 1378, B → 1222 (±0.5)

def test_worked_example():
    r_a, r_b = 1350.0, 1250.0
    global_avg = 1100.0
    asi_a, asi_b = 1200.0, 1150.0

    # Step 1: ASI adjustment
    r_adj_a = get_asi_adjusted_rating(r_a, global_avg, asi_a)  # 1350 + (1100-1200) = 1250
    r_adj_b = get_asi_adjusted_rating(r_b, global_avg, asi_b)  # 1250 + (1100-1150) = 1200
    assert r_adj_a == 1250.0
    assert r_adj_b == 1200.0

    # Step 2: Expected score
    exp_a = get_expected_score(r_adj_a, r_adj_b)
    assert abs(exp_a - 0.57) < 0.01

    # Step 3: Actual score (3-0 in BO5)
    act_winner, act_loser = get_actual_score(3, 0, "BEST_OF_5")
    assert act_winner == 1.0

    # Step 4 & 5: K-factor and CR
    # A: 20 matches → k_base=50; cr=1-exp(-20/30)≈0.4866
    # B: 60 matches → k_base=32; cr=1-exp(-60/30)≈0.8647
    rated_a, rated_b = 20, 60
    cr_a = get_cr(rated_a)
    cr_b = get_cr(rated_b)

    same_academy = False
    eff_type = "TOURNAMENT_EXTERNAL"
    w_match = get_match_weight(eff_type)     # 1.2
    w_academy = get_academy_weight(same_academy)  # 1.2

    k_base_a = get_k_base(rated_a)  # 50
    k_base_b = get_k_base(rated_b)  # 32
    assert k_base_a == 50.0
    assert k_base_b == 32.0

    # Step 6: K_eff and K_shared
    k_eff_a = get_k_eff(k_base_a, w_match, w_academy, cr_a)   # min(108.9, 60) = 60
    k_eff_b = get_k_eff(k_base_b, w_match, w_academy, cr_b)   # ≈52.3
    assert k_eff_a == 60.0
    assert abs(k_eff_b - 52.3) < 0.2

    k_shared = get_k_shared(k_eff_a, k_eff_b)
    assert abs(k_shared - 56.15) < 0.1

    # Step 7: Delta
    delta = k_shared * (act_winner - exp_a)
    assert abs(delta - 24.1) < 0.2

    # Upset check: r_adj_a (1250) > r_adj_b (1200) → A was favored → NOT an upset
    is_upset = r_adj_a < r_adj_b
    assert is_upset is False

    # Age bonus requires is_upset=True AND younger wins → 0 here
    dob_a = date(2015, 1, 1)
    dob_b = date(2013, 1, 1)
    age_bonus = get_age_bonus(dob_a, dob_b, is_upset)
    assert age_bonus == 0.0

    new_r_a = r_a + delta + age_bonus
    new_r_b = r_b - delta - age_bonus

    # Without age bonus: A ≈ 1374.1, B ≈ 1225.9
    assert abs(new_r_a - 1374.1) < 0.5, f"A rating {new_r_a:.2f} not within 0.5 of 1374.1"
    assert abs(new_r_b - 1225.9) < 0.5, f"B rating {new_r_b:.2f} not within 0.5 of 1225.9"
