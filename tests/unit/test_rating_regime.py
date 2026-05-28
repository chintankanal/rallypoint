"""
Tests for app/services/rating_regime.py and fixture_config.py.
"""
from app.services.fixture_config import (
    DEFAULT_FIXTURE_CONFIG,
    FixtureConfig,
    with_overrides,
    _from_cfg_dict,
)
from app.services.rating_regime import (
    REGIME_DEVELOPING,
    REGIME_ELITE_PROXIMITY,
    REGIME_HIGH_LEVEL,
    REGIME_VOLATILE_LOW,
    detect_player_regime,
    detect_pool_regime,
    regime_thresholds,
)


# ── fixture_config ────────────────────────────────────────────────────────────

def test_fixture_config_defaults_match_phase2_constants():
    cfg = DEFAULT_FIXTURE_CONFIG
    assert cfg.competitive_max_gap == 100.0
    assert cfg.stretch_max_gap == 250.0
    assert cfg.max_exception_gap == 500.0


def test_fixture_config_from_db_cfg_uses_provided_values():
    cfg = _from_cfg_dict({
        "fixture_competitive_max_gap": 75,
        "fixture_stretch_max_gap": 200,
    })
    assert cfg.competitive_max_gap == 75.0
    assert cfg.stretch_max_gap == 200.0
    # Unspecified keys fall back to defaults.
    assert cfg.max_exception_gap == 500.0


def test_fixture_config_with_overrides_returns_new_instance():
    base = DEFAULT_FIXTURE_CONFIG
    overridden = with_overrides(base, competitive_max_gap=80.0)
    assert overridden.competitive_max_gap == 80.0
    assert base.competitive_max_gap == 100.0  # base unchanged (frozen)


# ── detect_player_regime ──────────────────────────────────────────────────────

def test_provisional_player_is_volatile_low():
    assert detect_player_regime(1500.0, total_matches=2) == REGIME_VOLATILE_LOW
    assert detect_player_regime(1800.0, total_matches=50, is_provisional=True) == REGIME_VOLATILE_LOW


def test_below_volatile_low_threshold_is_volatile_low():
    assert detect_player_regime(800.0, total_matches=50) == REGIME_VOLATILE_LOW


def test_developing_band():
    assert detect_player_regime(1000.0, total_matches=50) == REGIME_DEVELOPING
    assert detect_player_regime(1300.0, total_matches=50) == REGIME_DEVELOPING


def test_high_level_band():
    assert detect_player_regime(1500.0, total_matches=50) == REGIME_HIGH_LEVEL
    assert detect_player_regime(1900.0, total_matches=50) == REGIME_HIGH_LEVEL


def test_elite_proximity_by_absolute_rating():
    assert detect_player_regime(2100.0, total_matches=50) == REGIME_ELITE_PROXIMITY


def test_elite_proximity_via_national_track_hybrid():
    assert detect_player_regime(
        1600.0, total_matches=50, tier="NATIONAL_TRACK",
    ) == REGIME_ELITE_PROXIMITY


def test_national_track_without_maturity_not_elite_proximity():
    """The NATIONAL_TRACK hybrid trigger requires sufficient match history."""
    assert detect_player_regime(
        1600.0, total_matches=10, tier="NATIONAL_TRACK",
    ) == REGIME_HIGH_LEVEL


# ── regime_thresholds ─────────────────────────────────────────────────────────

def test_regime_thresholds_tighten_with_skill():
    """Elite-proximity caps must be tighter than developing caps (critique §8)."""
    cfg = DEFAULT_FIXTURE_CONFIG
    dev = regime_thresholds(REGIME_DEVELOPING, cfg=cfg)
    elite = regime_thresholds(REGIME_ELITE_PROXIMITY, cfg=cfg)
    assert elite.competitive_max_gap < dev.competitive_max_gap
    assert elite.stretch_max_gap < dev.stretch_max_gap


def test_regime_thresholds_relax_for_volatile_low():
    """VOLATILE_LOW caps must be wider than DEVELOPING (noisy ratings, loose gaps)."""
    cfg = DEFAULT_FIXTURE_CONFIG
    vol = regime_thresholds(REGIME_VOLATILE_LOW, cfg=cfg)
    dev = regime_thresholds(REGIME_DEVELOPING, cfg=cfg)
    assert vol.competitive_max_gap >= dev.competitive_max_gap
    assert vol.stretch_max_gap >= dev.stretch_max_gap


# ── detect_pool_regime ────────────────────────────────────────────────────────

def test_pool_regime_picks_majority():
    """Pool regime classification picks the regime with the most players."""
    players = [
        {"player_id": "a", "current_rating": 1500.0, "rated_matches_completed": 40},
        {"player_id": "b", "current_rating": 1600.0, "rated_matches_completed": 40},
        {"player_id": "c", "current_rating": 1700.0, "rated_matches_completed": 40},
        # one outlier
        {"player_id": "d", "current_rating": 800.0,  "rated_matches_completed": 40},
    ]
    assert detect_pool_regime(players) == REGIME_HIGH_LEVEL


def test_pool_regime_with_no_players_defaults_to_developing():
    assert detect_pool_regime([]) == REGIME_DEVELOPING


def test_pool_regime_respects_provisional_signal():
    """A pool of mostly-provisional players sits in VOLATILE_LOW even if ratings are high."""
    players = [
        {"player_id": str(i), "current_rating": 1600.0, "is_provisional": True}
        for i in range(4)
    ]
    assert detect_pool_regime(players) == REGIME_VOLATILE_LOW
