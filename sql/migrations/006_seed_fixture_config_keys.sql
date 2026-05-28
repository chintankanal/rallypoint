-- Phase 5 of the fixture engine redesign — config-driven thresholds
-- (docs/fixture_engine_phased_impl_plan.md §5a, critique §8).
--
-- Adds the fixture_* keys read by app/services/fixture_config.py. Defaults
-- intentionally match the module constants the Phase 2 engine hardcoded, so
-- behavior is unchanged on a fresh install — these are knobs for tuning per
-- deployment without code changes.

INSERT INTO system_configuration (key, value, description) VALUES
    ('fixture_competitive_max_gap',      '100', 'Gap (rating points) below which a pair is gap_band=COMPETITIVE'),
    ('fixture_stretch_max_gap',          '250', 'Upper bound of gap_band=STRETCH; gaps above this become OUT_OF_BAND'),
    ('fixture_max_exception_gap',        '500', 'Hard cap on any pairing; must stay <= rating_gap_threshold (match eligibility cap)'),
    ('fixture_discovery_spread_max',     '100', 'detect_phase: spread <= this → DISCOVERY (critique §18)'),
    ('fixture_transition_spread_max',    '250', 'detect_phase: spread <= this → TRANSITION; above → STANDARD'),
    ('fixture_small_session_threshold',  '6',   'Sessions with fewer than this many players use pure round-robin (critique §19)'),
    ('fixture_core_spread_p_low',        '10',  'Percentile used for the low end of core_spread (critique §7)'),
    ('fixture_core_spread_p_high',       '90',  'Percentile used for the high end of core_spread (critique §7)'),
    ('fixture_provisional_majority_threshold', '0.6', 'Fraction of provisional players above which the session is forced to DISCOVERY phase'),
    ('fixture_max_recent_matches_same_pair', '3', 'Hard cap on rematch count within the recent window (rematch policy)'),
    ('fixture_repeat_count_penalty',     '250', 'Solver cost per prior meeting in the recent window'),
    ('fixture_same_session_penalty',     '500', 'Solver cost added when the pair already plays this session'),
    ('fixture_regime_volatile_low_max',  '900',  'Upper bound of VOLATILE_LOW rating regime (engine-internal, critique §8)'),
    ('fixture_regime_developing_max',    '1400', 'Upper bound of DEVELOPING rating regime'),
    ('fixture_regime_high_level_max',    '2000', 'Upper bound of HIGH_LEVEL rating regime; >= this → ELITE_PROXIMITY'),
    ('fixture_regime_volatile_low_competitive_max', '150', 'Per-regime override for competitive gap cap (VOLATILE_LOW: wider)'),
    ('fixture_regime_volatile_low_stretch_max',     '350', 'Per-regime override for stretch gap cap (VOLATILE_LOW: wider)'),
    ('fixture_regime_developing_competitive_max',   '100', 'Per-regime competitive cap (DEVELOPING: baseline)'),
    ('fixture_regime_developing_stretch_max',       '250', 'Per-regime stretch cap (DEVELOPING: baseline)'),
    ('fixture_regime_high_level_competitive_max',   '75',  'Per-regime competitive cap (HIGH_LEVEL: tighter)'),
    ('fixture_regime_high_level_stretch_max',       '200', 'Per-regime stretch cap (HIGH_LEVEL: tighter)'),
    ('fixture_regime_elite_proximity_competitive_max', '60', 'Per-regime competitive cap (ELITE_PROXIMITY: tightest)'),
    ('fixture_regime_elite_proximity_stretch_max',     '150', 'Per-regime stretch cap (ELITE_PROXIMITY: tightest)')
ON CONFLICT (key) DO NOTHING;
