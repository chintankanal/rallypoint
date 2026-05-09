import math
from datetime import date


def get_tier(rating: float) -> str:
    if rating < 900:
        return "BEGINNER"
    if rating < 1100:
        return "INTERMEDIATE"
    if rating < 1300:
        return "ADVANCED"
    if rating < 1500:
        return "ELITE"
    return "NATIONAL_TRACK"


def get_cr(total_matches: int) -> float:
    """Confidence Ratio: 1 - exp(-n/30)."""
    return 1 - math.exp(-total_matches / 30)


def get_age_as_of_jan1(dob: date, reference_year: int | None = None) -> int:
    year = reference_year or date.today().year
    jan1 = date(year, 1, 1)
    return jan1.year - dob.year - ((jan1.month, jan1.day) < (dob.month, dob.day))


def get_age_group(age_as_of_jan1: int) -> str:
    if age_as_of_jan1 <= 10:
        return "U10"
    if age_as_of_jan1 <= 13:
        return "U13"
    if age_as_of_jan1 <= 15:
        return "U15"
    if age_as_of_jan1 <= 17:
        return "U17"
    return "OPEN"


def get_k_base(rated_matches: int) -> float:
    if rated_matches < 30:
        return 50.0
    if rated_matches < 100:
        return 32.0
    return 20.0


def get_match_weight(effective_event_type: str) -> float:
    weights = {
        "LEAGUE": 1.0,
        "TOURNAMENT_EXTERNAL": 1.2,
        "TOURNAMENT_MANAGED": 1.2,
        "FRIENDLY": 0.5,
    }
    return weights.get(effective_event_type, 1.0)


def get_academy_weight(same_academy: bool) -> float:
    return 0.8 if same_academy else 1.2


def get_k_eff(k_base: float, w_match: float, w_academy: float, cr: float) -> float:
    return min(k_base * w_match * w_academy * (2 - cr), 60.0)


def get_k_shared(k_eff_a: float, k_eff_b: float) -> float:
    return (k_eff_a + k_eff_b) / 2


def get_expected_score(r_adj_a: float, r_adj_b: float) -> float:
    return 1 / (1 + 10 ** ((r_adj_b - r_adj_a) / 400))


# Margin-of-victory actual score tables
_ACTUAL_SCORES: dict[str, dict[tuple[int, int], tuple[float, float]]] = {
    "BEST_OF_3": {
        (2, 0): (1.0, 0.0),
        (2, 1): (0.75, 0.25),
    },
    "BEST_OF_5": {
        (3, 0): (1.0, 0.0),
        (3, 1): (0.85, 0.15),
        (3, 2): (0.65, 0.35),
    },
    "BEST_OF_7": {
        (4, 0): (1.0, 0.0),
        (4, 1): (0.875, 0.125),
        (4, 2): (0.75, 0.25),
        (4, 3): (0.625, 0.375),
    },
}


def get_actual_score(
    sets_won_winner: int, sets_won_loser: int, match_format: str
) -> tuple[float, float]:
    """Return (winner_score, loser_score) from margin-of-victory table."""
    fmt = match_format.upper()
    key = (sets_won_winner, sets_won_loser)
    scores = _ACTUAL_SCORES.get(fmt, {})
    if key not in scores:
        raise ValueError(
            f"Invalid set score {sets_won_winner}-{sets_won_loser} for format {match_format}"
        )
    return scores[key]


def get_age_bonus(winner_dob: date, loser_dob: date, is_upset: bool) -> float:
    """
    Return age bonus points when a rating-upset occurs AND the younger player won.
    is_upset = winner's R_adj < loser's R_adj (lower-rated player won).
    age_diff = floor((winner_dob - loser_dob).days / 365.25); positive = winner is younger.
    """
    if not is_upset:
        return 0.0
    age_diff_years = math.floor((winner_dob - loser_dob).days / 365.25)
    if age_diff_years <= 0:
        return 0.0
    return min(10.0, 2.0 * age_diff_years)


def get_asi_adjusted_rating(
    player_rating: float, global_avg: float, asi: float
) -> float:
    return player_rating + (global_avg - asi)


def get_effective_event_type(
    event_type: str, diminishing_signal_applied: bool
) -> str:
    return "FRIENDLY" if diminishing_signal_applied else event_type
