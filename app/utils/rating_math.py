import math
from datetime import date
from threading import Lock
from cachetools import TTLCache

# ── Config cache: one entry, 60-second TTL ────────────────────────────────────
_config_cache: TTLCache = TTLCache(maxsize=1, ttl=60)
_cache_lock = Lock()

# ── Default values (used as fallbacks) ────────────────────────────────────────
_DEFAULTS = {
    "tier_beginner_max": 899.0,
    "tier_intermediate_max": 1099.0,
    "tier_advanced_max": 1299.0,
    "tier_elite_max": 1499.0,
    "k_base_provisional": 50.0,
    "k_base_intermediate": 32.0,
    "k_base_established": 20.0,
    "k_base_provisional_threshold": 30.0,
    "k_base_intermediate_threshold": 100.0,
    "k_max": 60.0,
    "w_league": 1.0,
    "w_tournament": 1.2,
    "w_friendly": 0.5,
    "w_same_academy": 0.8,
    "w_cross_academy": 1.2,
    "cr_match_threshold": 30.0,
    "elo_divisor": 400.0,
    "age_bonus_max": 10.0,
    "age_bonus_multiplier": 2.0,
    "age_group_u11_max": 11.0,
    "age_group_u13_max": 13.0,
    "age_group_u15_max": 15.0,
    "age_group_u17_max": 17.0,
}


def _load_config() -> dict[str, float]:
    """Load config from system_configuration table with 60s TTL cache."""
    with _cache_lock:
        cached = _config_cache.get("cfg")
        if cached is not None:
            return cached
        
        try:
            from app.database import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT key, value FROM system_configuration")
                    rows = cur.fetchall()
                    cfg = {r["key"]: float(r["value"]) for r in rows}
        except Exception:
            # Fallback to defaults if DB unavailable
            cfg = _DEFAULTS.copy()
        
        # Fill in any missing keys with defaults
        for key, default_val in _DEFAULTS.items():
            cfg.setdefault(key, default_val)
        
        _config_cache["cfg"] = cfg
        return cfg


def invalidate_config_cache() -> None:
    """Call after PATCH /config to force next read to hit the DB."""
    with _cache_lock:
        _config_cache.clear()


def get_tier(rating: float, cfg: dict[str, float] | None = None) -> str:
    if cfg is None:
        cfg = _load_config()
    
    beginner_max = cfg.get("tier_beginner_max", _DEFAULTS["tier_beginner_max"])
    intermediate_max = cfg.get("tier_intermediate_max", _DEFAULTS["tier_intermediate_max"])
    advanced_max = cfg.get("tier_advanced_max", _DEFAULTS["tier_advanced_max"])
    elite_max = cfg.get("tier_elite_max", _DEFAULTS["tier_elite_max"])
    
    if rating <= beginner_max:
        return "BEGINNER"
    if rating <= intermediate_max:
        return "INTERMEDIATE"
    if rating <= advanced_max:
        return "ADVANCED"
    if rating <= elite_max:
        return "ELITE"
    return "NATIONAL_TRACK"


def get_cr(total_matches: int, cfg: dict[str, float] | None = None) -> float:
    """Confidence Ratio: 1 - exp(-n / cr_match_threshold)."""
    if cfg is None:
        cfg = _load_config()
    
    threshold = cfg.get("cr_match_threshold", _DEFAULTS["cr_match_threshold"])
    return 1 - math.exp(-total_matches / threshold)


def get_age_as_of_jan1(dob: date, reference_year: int | None = None) -> int:
    year = reference_year or date.today().year
    jan1 = date(year, 1, 1)
    return jan1.year - dob.year - ((jan1.month, jan1.day) < (dob.month, dob.day))


def get_age_group(age_as_of_jan1: int, cfg: dict[str, float] | None = None) -> str:
    if cfg is None:
        cfg = _load_config()
    
    u11_max = cfg.get(
        "age_group_u11_max",
        cfg.get("age_group_u10_max", _DEFAULTS["age_group_u11_max"]),
    )
    u13_max = cfg.get("age_group_u13_max", _DEFAULTS["age_group_u13_max"])
    u15_max = cfg.get("age_group_u15_max", _DEFAULTS["age_group_u15_max"])
    u17_max = cfg.get("age_group_u17_max", _DEFAULTS["age_group_u17_max"])
    
    if age_as_of_jan1 <= u11_max:
        return "U11"
    if age_as_of_jan1 <= u13_max:
        return "U13"
    if age_as_of_jan1 <= u15_max:
        return "U15"
    if age_as_of_jan1 <= u17_max:
        return "U17"
    return "OPEN"


def get_k_base(rated_matches: int, cfg: dict[str, float] | None = None) -> float:
    if cfg is None:
        cfg = _load_config()
    
    prov_threshold = cfg.get("k_base_provisional_threshold", _DEFAULTS["k_base_provisional_threshold"])
    inter_threshold = cfg.get("k_base_intermediate_threshold", _DEFAULTS["k_base_intermediate_threshold"])
    k_prov = cfg.get("k_base_provisional", _DEFAULTS["k_base_provisional"])
    k_inter = cfg.get("k_base_intermediate", _DEFAULTS["k_base_intermediate"])
    k_est = cfg.get("k_base_established", _DEFAULTS["k_base_established"])
    
    if rated_matches < prov_threshold:
        return k_prov
    if rated_matches < inter_threshold:
        return k_inter
    return k_est


def get_match_weight(effective_event_type: str, cfg: dict[str, float] | None = None) -> float:
    if cfg is None:
        cfg = _load_config()
    
    weights = {
        "LEAGUE": cfg.get("w_league", _DEFAULTS["w_league"]),
        "TOURNAMENT_EXTERNAL": cfg.get("w_tournament", _DEFAULTS["w_tournament"]),
        "TOURNAMENT_MANAGED": cfg.get("w_tournament", _DEFAULTS["w_tournament"]),
        "FRIENDLY": cfg.get("w_friendly", _DEFAULTS["w_friendly"]),
    }
    return weights.get(effective_event_type, 1.0)


def get_academy_weight(same_academy: bool, cfg: dict[str, float] | None = None) -> float:
    if cfg is None:
        cfg = _load_config()
    
    if same_academy:
        return cfg.get("w_same_academy", _DEFAULTS["w_same_academy"])
    else:
        return cfg.get("w_cross_academy", _DEFAULTS["w_cross_academy"])


def get_k_eff(k_base: float, w_match: float, w_academy: float, cr: float, cfg: dict[str, float] | None = None) -> float:
    if cfg is None:
        cfg = _load_config()
    
    k_max = cfg.get("k_max", _DEFAULTS["k_max"])
    return min(k_base * w_match * w_academy * (2 - cr), k_max)


def get_k_shared(k_eff_a: float, k_eff_b: float) -> float:
    return (k_eff_a + k_eff_b) / 2


def get_expected_score(r_adj_a: float, r_adj_b: float, cfg: dict[str, float] | None = None) -> float:
    if cfg is None:
        cfg = _load_config()
    
    divisor = cfg.get("elo_divisor", _DEFAULTS["elo_divisor"])
    return 1 / (1 + 10 ** ((r_adj_b - r_adj_a) / divisor))


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


def get_age_bonus(winner_dob: date, loser_dob: date, is_upset: bool, cfg: dict[str, float] | None = None) -> float:
    """
    Return age bonus points when a rating-upset occurs AND the younger player won.
    is_upset = winner's R_adj < loser's R_adj (lower-rated player won).
    age_diff = floor((winner_dob - loser_dob).days / 365.25); positive = winner is younger.
    """
    if cfg is None:
        cfg = _load_config()
    
    if not is_upset:
        return 0.0
    
    age_diff_years = math.floor((winner_dob - loser_dob).days / 365.25)
    if age_diff_years <= 0:
        return 0.0
    
    bonus_max = cfg.get("age_bonus_max", _DEFAULTS["age_bonus_max"])
    bonus_mult = cfg.get("age_bonus_multiplier", _DEFAULTS["age_bonus_multiplier"])
    
    return min(bonus_max, bonus_mult * age_diff_years)


def get_asi_adjusted_rating(
    player_rating: float, global_avg: float, asi: float
) -> float:
    return player_rating + (global_avg - asi)


def get_effective_event_type(
    event_type: str, diminishing_signal_applied: bool
) -> str:
    return "FRIENDLY" if diminishing_signal_applied else event_type
