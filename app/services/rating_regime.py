"""
rating_regime — engine-facing rating regime classifier (critique §8).

The fixture engine uses regimes (VOLATILE_LOW / DEVELOPING / HIGH_LEVEL /
ELITE_PROXIMITY) to calibrate gap-band thresholds and rematch tolerance to the
band of play. This is *engine-internal* — visible program tiers (BEGINNER,
INTERMEDIATE, ADVANCED, ELITE, NATIONAL_TRACK) remain unchanged and are still
used by UI, reporting, and product flows.

Inputs the classifier consumes per player:
- absolute current_rating
- maturity (total_matches = rated_matches_completed + virtual_matches)
- provisional flag (derived from total_matches < provisional_threshold)
- tier label (NATIONAL_TRACK contributes to the ELITE_PROXIMITY hybrid trigger)

The module is pure-Python with no DB access. Defaults align with
fixture_config.DEFAULT_FIXTURE_CONFIG.
"""
from dataclasses import dataclass

from app.services.fixture_config import FixtureConfig, DEFAULT_FIXTURE_CONFIG

REGIME_VOLATILE_LOW = "VOLATILE_LOW"
REGIME_DEVELOPING = "DEVELOPING"
REGIME_HIGH_LEVEL = "HIGH_LEVEL"
REGIME_ELITE_PROXIMITY = "ELITE_PROXIMITY"

REGIMES = (
    REGIME_VOLATILE_LOW,
    REGIME_DEVELOPING,
    REGIME_HIGH_LEVEL,
    REGIME_ELITE_PROXIMITY,
)


@dataclass(frozen=True)
class RegimeThresholds:
    """Per-regime gap caps that the solver consults."""
    name: str
    competitive_max_gap: float
    stretch_max_gap: float


def detect_player_regime(
    rating: float,
    total_matches: int,
    *,
    is_provisional: bool = False,
    tier: str | None = None,
    cfg: FixtureConfig = DEFAULT_FIXTURE_CONFIG,
) -> str:
    """
    Classify a single player into an engine regime.

    Rules (critique §8 first-pass):
      - VOLATILE_LOW: rating < regime_volatile_low_max OR provisional / very
        low maturity. Pairing should treat gaps loosely.
      - DEVELOPING: regime_volatile_low_max <= rating < regime_developing_max.
        The baseline regime.
      - HIGH_LEVEL: regime_developing_max <= rating < regime_high_level_max.
      - ELITE_PROXIMITY: rating >= regime_high_level_max, OR (tier ==
        NATIONAL_TRACK and not provisional and total_matches sufficient).
    """
    # Provisional / low maturity players always start at VOLATILE_LOW so the
    # solver doesn't over-react to noisy ratings.
    if is_provisional or total_matches < 5:
        return REGIME_VOLATILE_LOW

    if rating >= cfg.regime_high_level_max:
        return REGIME_ELITE_PROXIMITY
    if tier == "NATIONAL_TRACK" and total_matches >= 30:
        return REGIME_ELITE_PROXIMITY
    if rating >= cfg.regime_developing_max:
        return REGIME_HIGH_LEVEL
    if rating >= cfg.regime_volatile_low_max:
        return REGIME_DEVELOPING
    return REGIME_VOLATILE_LOW


def regime_thresholds(
    regime: str, cfg: FixtureConfig = DEFAULT_FIXTURE_CONFIG,
) -> RegimeThresholds:
    """Return the gap-band thresholds for a given regime."""
    if regime == REGIME_VOLATILE_LOW:
        return RegimeThresholds(
            REGIME_VOLATILE_LOW,
            cfg.regime_volatile_low_competitive_max,
            cfg.regime_volatile_low_stretch_max,
        )
    if regime == REGIME_HIGH_LEVEL:
        return RegimeThresholds(
            REGIME_HIGH_LEVEL,
            cfg.regime_high_level_competitive_max,
            cfg.regime_high_level_stretch_max,
        )
    if regime == REGIME_ELITE_PROXIMITY:
        return RegimeThresholds(
            REGIME_ELITE_PROXIMITY,
            cfg.regime_elite_proximity_competitive_max,
            cfg.regime_elite_proximity_stretch_max,
        )
    # Default / DEVELOPING
    return RegimeThresholds(
        REGIME_DEVELOPING,
        cfg.regime_developing_competitive_max,
        cfg.regime_developing_stretch_max,
    )


def detect_pool_regime(
    players: list[dict],
    *,
    cfg: FixtureConfig = DEFAULT_FIXTURE_CONFIG,
) -> str:
    """
    Determine the dominant regime in a pool, used to calibrate pool-level
    thresholds. We pick the regime that the median rating belongs to (median
    is more robust to outliers than mean).

    Players are expected to be dicts with `current_rating` and may carry
    optional fields:
      - `rated_matches_completed`, `virtual_matches` (for maturity)
      - `tier` (for the NATIONAL_TRACK hybrid trigger)
      - `is_provisional` (bool)
    """
    if not players:
        return REGIME_DEVELOPING

    counts: dict[str, int] = {r: 0 for r in REGIMES}
    for p in players:
        rating = float(p["current_rating"])
        total = int(p.get("rated_matches_completed", 0)) + int(p.get("virtual_matches", 0))
        is_prov = bool(p.get("is_provisional", False))
        tier = p.get("tier")
        regime = detect_player_regime(
            rating, total, is_provisional=is_prov, tier=tier, cfg=cfg,
        )
        counts[regime] += 1

    # Pick the regime with the most players; ties broken by REGIMES order so
    # the result is deterministic.
    return max(REGIMES, key=lambda r: (counts[r], -REGIMES.index(r)))
