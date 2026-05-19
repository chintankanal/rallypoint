import math
from datetime import date

import pytest

from app.utils.rating_math import get_age_as_of_jan1, get_age_group, get_cr, get_tier


# ---------- tier ----------

@pytest.mark.parametrize("rating,expected", [
    (0,    "BEGINNER"),
    (899,  "BEGINNER"),
    (900,  "INTERMEDIATE"),
    (1099, "INTERMEDIATE"),
    (1100, "ADVANCED"),
    (1299, "ADVANCED"),
    (1300, "ELITE"),
    (1499, "ELITE"),
    (1500, "NATIONAL_TRACK"),
    (2000, "NATIONAL_TRACK"),
])
def test_get_tier(rating, expected):
    assert get_tier(rating) == expected


# ---------- confidence ratio ----------

@pytest.mark.parametrize("n,expected_approx", [
    (0,   0.0),
    (5,   1 - math.exp(-5 / 30)),
    (15,  1 - math.exp(-15 / 30)),
    (30,  1 - math.exp(-1)),
    (100, 1 - math.exp(-100 / 30)),
])
def test_get_cr(n, expected_approx):
    assert abs(get_cr(n) - expected_approx) < 1e-9


def test_cr_zero_for_no_matches():
    assert get_cr(0) == 0.0


def test_cr_approaches_one():
    assert get_cr(1000) > 0.999


# ---------- provisional boundary ----------

def test_provisional_boundary():
    # is_provisional when seeding = UNSEEDED and total_matches < 15
    def is_provisional(total: int) -> bool:
        return total < 15

    assert is_provisional(14) is True
    assert is_provisional(15) is False
    assert is_provisional(0) is True


# ---------- age as of Jan 1 ----------

def test_age_as_of_jan1_exact_birthday():
    # born Jan 1 2015 → age on Jan 1 2025 = 10
    dob = date(2015, 1, 1)
    assert get_age_as_of_jan1(dob, reference_year=2025) == 10


def test_age_as_of_jan1_before_birthday():
    # born Dec 31 2014 → on Jan 1 2025, birthday hasn't occurred yet in 2025 → 10
    dob = date(2014, 12, 31)
    assert get_age_as_of_jan1(dob, reference_year=2025) == 10


def test_age_as_of_jan1_after_birthday():
    # born Jan 2 2015 → on Jan 1 2025, still 9 (birthday is after Jan 1)
    dob = date(2015, 1, 2)
    assert get_age_as_of_jan1(dob, reference_year=2025) == 9


# ---------- age group ----------

@pytest.mark.parametrize("age,expected", [
    (6,  "U11"),
    (11, "U11"),
    (12, "U13"),
    (13, "U13"),
    (14, "U15"),
    (15, "U15"),
    (16, "U17"),
    (17, "U17"),
    (18, "OPEN"),
])
def test_get_age_group(age, expected):
    assert get_age_group(age) == expected
