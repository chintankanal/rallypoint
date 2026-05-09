-- Seed default system configuration values.
-- Run once after schema creation. Safe to re-run (ON CONFLICT DO NOTHING).

INSERT INTO system_configuration (key, value, description) VALUES
    ('global_average_rating',   '1000.00', 'Mean current_rating across all ACTIVE players; updated nightly by ASI job'),
    ('k_base_provisional',      '50',      'K-factor for players with <30 rated matches'),
    ('k_base_intermediate',     '32',      'K-factor for players with 30–99 rated matches'),
    ('k_base_established',      '20',      'K-factor for players with ≥100 rated matches'),
    ('k_max',                   '60',      'Hard cap on effective K-factor'),
    ('w_league',                '1.0',     'Match weight for LEAGUE event type'),
    ('w_tournament',            '1.2',     'Match weight for TOURNAMENT_EXTERNAL / TOURNAMENT_MANAGED'),
    ('w_friendly',              '0.5',     'Match weight for FRIENDLY event type'),
    ('w_same_academy',          '0.8',     'Academy weight when both players share an academy'),
    ('w_cross_academy',         '1.2',     'Academy weight when players are from different academies'),
    ('cr_match_threshold',      '30',      'Denominator in CR formula: 1 - exp(-n/30)'),
    ('provisional_threshold',   '15',      'Matches required before a player exits provisional status'),
    ('inactivity_weeks',        '8',       'Weeks without a match before inactivity decay activates'),
    ('rating_gap_threshold',    '500',     'Raw rating difference above which a match is ineligible'),
    ('diminishing_signal_days', '7',       'Window in days for diminishing signal check'),
    ('diminishing_signal_count','2',       'Pair must play ≥ this many times in window to trigger diminishing signal'),
    ('age_bonus_max',           '10',      'Maximum age bonus points per match'),
    ('tier_beginner_max',       '899',     'Upper boundary of BEGINNER tier (inclusive)'),
    ('tier_intermediate_max',   '1099',    'Upper boundary of INTERMEDIATE tier'),
    ('tier_advanced_max',       '1299',    'Upper boundary of ADVANCED tier'),
    ('tier_elite_max',          '1499',    'Upper boundary of ELITE tier')
ON CONFLICT (key) DO NOTHING;
