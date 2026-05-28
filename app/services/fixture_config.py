"""
fixture_config — typed accessor for fixture-engine thresholds backed by the
system_configuration table.

Per docs/fixture_engine_phased_impl_plan.md Phase 5 and critique §8, the
engine's gap thresholds, rematch parameters, and phase-detection boundaries
move out of module constants and into config rows so they can be tuned per
deployment without code changes.

The engine still operates on a plain FixtureConfig dataclass internally — this
module just owns the loader and defaults. It reuses the existing cached
_load_config() loader in app.utils.rating_math so a single PATCH /config call
invalidates all consumers consistently.
"""
from dataclasses import dataclass, replace
from threading import Lock
from typing import Optional

# Defaults are the same numbers Phase 2 hardcoded in fixture_engine.py — they
# stay in sync with rating_math's existing _DEFAULTS dict via _DEFAULT_KEYS.
_DEFAULT_FIXTURE_CFG = {
    # Gap bands (critique §2)
    "fixture_competitive_max_gap": 100.0,
    "fixture_stretch_max_gap": 250.0,
    # Hard cap; must stay <= rating_gap_threshold (the match_service eligibility cap)
    "fixture_max_exception_gap": 500.0,
    # Phase detection (critique §18, §19)
    "fixture_discovery_spread_max": 100.0,
    "fixture_transition_spread_max": 250.0,
    "fixture_small_session_threshold": 6.0,
    # Robust phase detection (critique §7)
    "fixture_core_spread_p_low": 10.0,   # percentile for low end
    "fixture_core_spread_p_high": 90.0,  # percentile for high end
    "fixture_provisional_majority_threshold": 0.6,  # if >= this fraction provisional → DISCOVERY
    # Rematch policy (critique §17)
    "fixture_max_recent_matches_same_pair": 3.0,
    "fixture_repeat_count_penalty": 250.0,
    "fixture_same_session_penalty": 500.0,
    # Regime thresholds (critique §8) — absolute rating cutoffs, with the
    # understanding that the elite cutoff also uses NATIONAL_TRACK +
    # confidence as a hybrid trigger in rating_regime.py.
    "fixture_regime_volatile_low_max": 900.0,
    "fixture_regime_developing_max": 1400.0,
    "fixture_regime_high_level_max": 2000.0,
    # Per-regime gap overrides
    "fixture_regime_volatile_low_competitive_max": 150.0,
    "fixture_regime_volatile_low_stretch_max": 350.0,
    "fixture_regime_developing_competitive_max": 100.0,
    "fixture_regime_developing_stretch_max": 250.0,
    "fixture_regime_high_level_competitive_max": 75.0,
    "fixture_regime_high_level_stretch_max": 200.0,
    "fixture_regime_elite_proximity_competitive_max": 60.0,
    "fixture_regime_elite_proximity_stretch_max": 150.0,
}


@dataclass(frozen=True)
class FixtureConfig:
    """Engine-facing config snapshot — frozen for thread-safe sharing."""
    competitive_max_gap: float = 100.0
    stretch_max_gap: float = 250.0
    max_exception_gap: float = 500.0
    discovery_spread_max: float = 100.0
    transition_spread_max: float = 250.0
    small_session_threshold: int = 6
    core_spread_p_low: float = 10.0
    core_spread_p_high: float = 90.0
    provisional_majority_threshold: float = 0.6
    max_recent_matches_same_pair: int = 3
    repeat_count_penalty: float = 250.0
    same_session_penalty: float = 500.0
    regime_volatile_low_max: float = 900.0
    regime_developing_max: float = 1400.0
    regime_high_level_max: float = 2000.0
    regime_volatile_low_competitive_max: float = 150.0
    regime_volatile_low_stretch_max: float = 350.0
    regime_developing_competitive_max: float = 100.0
    regime_developing_stretch_max: float = 250.0
    regime_high_level_competitive_max: float = 75.0
    regime_high_level_stretch_max: float = 200.0
    regime_elite_proximity_competitive_max: float = 60.0
    regime_elite_proximity_stretch_max: float = 150.0


# Default-defaults FixtureConfig — used when no DB is available (tests).
DEFAULT_FIXTURE_CONFIG = FixtureConfig()


_cache_lock = Lock()
_cached: Optional[FixtureConfig] = None


def _from_cfg_dict(cfg: dict[str, float]) -> FixtureConfig:
    """Build a FixtureConfig from a {key: float} dict loaded from DB."""
    g = lambda k, default: cfg.get(k, _DEFAULT_FIXTURE_CFG.get(k, default))  # noqa: E731
    return FixtureConfig(
        competitive_max_gap=float(g("fixture_competitive_max_gap", 100.0)),
        stretch_max_gap=float(g("fixture_stretch_max_gap", 250.0)),
        max_exception_gap=float(g("fixture_max_exception_gap", 500.0)),
        discovery_spread_max=float(g("fixture_discovery_spread_max", 100.0)),
        transition_spread_max=float(g("fixture_transition_spread_max", 250.0)),
        small_session_threshold=int(g("fixture_small_session_threshold", 6)),
        core_spread_p_low=float(g("fixture_core_spread_p_low", 10.0)),
        core_spread_p_high=float(g("fixture_core_spread_p_high", 90.0)),
        provisional_majority_threshold=float(g("fixture_provisional_majority_threshold", 0.6)),
        max_recent_matches_same_pair=int(g("fixture_max_recent_matches_same_pair", 3)),
        repeat_count_penalty=float(g("fixture_repeat_count_penalty", 250.0)),
        same_session_penalty=float(g("fixture_same_session_penalty", 500.0)),
        regime_volatile_low_max=float(g("fixture_regime_volatile_low_max", 900.0)),
        regime_developing_max=float(g("fixture_regime_developing_max", 1400.0)),
        regime_high_level_max=float(g("fixture_regime_high_level_max", 2000.0)),
        regime_volatile_low_competitive_max=float(g("fixture_regime_volatile_low_competitive_max", 150.0)),
        regime_volatile_low_stretch_max=float(g("fixture_regime_volatile_low_stretch_max", 350.0)),
        regime_developing_competitive_max=float(g("fixture_regime_developing_competitive_max", 100.0)),
        regime_developing_stretch_max=float(g("fixture_regime_developing_stretch_max", 250.0)),
        regime_high_level_competitive_max=float(g("fixture_regime_high_level_competitive_max", 75.0)),
        regime_high_level_stretch_max=float(g("fixture_regime_high_level_stretch_max", 200.0)),
        regime_elite_proximity_competitive_max=float(g("fixture_regime_elite_proximity_competitive_max", 60.0)),
        regime_elite_proximity_stretch_max=float(g("fixture_regime_elite_proximity_stretch_max", 150.0)),
    )


def load_fixture_config(force_refresh: bool = False) -> FixtureConfig:
    """
    Lazily load fixture config from system_configuration. Uses the cached
    rating_math _load_config() loader so a single PATCH /config invalidates
    both rating and fixture views.
    """
    global _cached
    if not force_refresh and _cached is not None:
        return _cached
    try:
        from app.utils.rating_math import _load_config
        cfg = _load_config()
    except Exception:
        cfg = {}
    with _cache_lock:
        _cached = _from_cfg_dict(cfg)
        return _cached


def invalidate_fixture_config_cache() -> None:
    """Call after a config update so the next load hits the DB."""
    global _cached
    with _cache_lock:
        _cached = None


def with_overrides(base: FixtureConfig, **overrides) -> FixtureConfig:
    """Construct a FixtureConfig with specific fields replaced — used by tests."""
    return replace(base, **overrides)
