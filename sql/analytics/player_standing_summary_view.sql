-- Create a consolidated view combining player standings, match aggregations, and latest rating transitions
DROP VIEW IF EXISTS player_standing_summary;
CREATE OR REPLACE VIEW player_standing_summary AS
WITH player_match_stats AS (
    SELECT 
        p.player_id,
        COUNT(m.match_id) AS total_matches_played,
        COUNT(CASE WHEN m.winner_id = p.player_id THEN 1 END) AS total_wins,
        COUNT(CASE WHEN m.winner_id != p.player_id THEN 1 END) AS total_losses,
        -- Sets won & lost
        SUM(CASE WHEN m.player_a_id = p.player_id THEN m.sets_won_a ELSE m.sets_won_b END) AS total_sets_won,
        SUM(CASE WHEN m.player_a_id = p.player_id THEN m.sets_won_b ELSE m.sets_won_a END) AS total_sets_lost
    FROM player p
    LEFT JOIN match m ON (p.player_id = m.player_a_id OR p.player_id = m.player_b_id)
                      AND m.confirmation_status != 'VOIDED'
    GROUP BY p.player_id
),
tier_config AS (
    SELECT 
        COALESCE(MAX(CASE WHEN key = 'tier_beginner_max' THEN value::decimal END), 899.0) AS beginner_max,
        COALESCE(MAX(CASE WHEN key = 'tier_intermediate_max' THEN value::decimal END), 1099.0) AS intermediate_max,
        COALESCE(MAX(CASE WHEN key = 'tier_advanced_max' THEN value::decimal END), 1299.0) AS advanced_max,
        COALESCE(MAX(CASE WHEN key = 'tier_elite_max' THEN value::decimal END), 1499.0) AS elite_max
    FROM system_configuration
),
player_latest_rating_change AS (
    -- Get the last rating change details for each player based on match chronology
    SELECT DISTINCT ON (rh.player_id)
        rh.player_id,
        rh.rating_before,
        rh.rating_after,
        rh.delta AS last_rating_change,
        rh.created_at AS last_rating_change_at
    FROM rating_history rh
    INNER JOIN match m ON rh.match_id = m.match_id
    WHERE rh.is_rollback = FALSE
      AND m.confirmation_status != 'VOIDED'
    ORDER BY rh.player_id, m.match_timestamp DESC, rh.created_at DESC
),
player_first_rating_change AS (
    -- Get the first rating change details for each player based on match chronology
    SELECT DISTINCT ON (rh.player_id)
        rh.player_id,
        rh.rating_before AS start_rating,
        rh.tier_before AS start_tier
    FROM rating_history rh
    INNER JOIN match m ON rh.match_id = m.match_id
    WHERE rh.is_rollback = FALSE
      AND m.confirmation_status != 'VOIDED'
    ORDER BY rh.player_id, m.match_timestamp ASC, rh.created_at ASC
)
SELECT 
    p.player_id,
    p.name AS player_name,
    p.gender,
    p.date_of_birth,
    p.nationality,
    p.status AS player_status,
    p.seeding_level,
    
    -- Rating standing progress
    COALESCE(pfrc.start_rating, p.current_rating) AS start_rating,
    p.current_rating,
    p.current_rating - COALESCE(pfrc.start_rating, p.current_rating) AS delta_rating,
    
    -- Dynamic Current Tier
    CASE 
        WHEN p.current_rating <= tc.beginner_max THEN 'BEGINNER'::tier
        WHEN p.current_rating <= tc.intermediate_max THEN 'INTERMEDIATE'::tier
        WHEN p.current_rating <= tc.advanced_max THEN 'ADVANCED'::tier
        WHEN p.current_rating <= tc.elite_max THEN 'ELITE'::tier
        ELSE 'NATIONAL_TRACK'::tier
    END AS current_tier,
    
    -- Starting Tier
    COALESCE(pfrc.start_tier, CASE 
        WHEN p.current_rating <= tc.beginner_max THEN 'BEGINNER'::tier
        WHEN p.current_rating <= tc.intermediate_max THEN 'INTERMEDIATE'::tier
        WHEN p.current_rating <= tc.advanced_max THEN 'ADVANCED'::tier
        WHEN p.current_rating <= tc.elite_max THEN 'ELITE'::tier
        ELSE 'NATIONAL_TRACK'::tier
    END) AS start_tier,
    
    a.name AS primary_academy_name,
    a.city AS academy_city,
    a.state AS academy_state,
    
    -- Match Stats
    COALESCE(pms.total_matches_played, 0) AS matches_played,
    COALESCE(pms.total_wins, 0) AS matches_won,
    COALESCE(pms.total_losses, 0) AS matches_lost,
    CASE 
        WHEN COALESCE(pms.total_matches_played, 0) > 0 
        THEN ROUND((COALESCE(pms.total_wins, 0)::decimal / pms.total_matches_played) * 100, 2)
        ELSE 0.00
    END AS win_rate_percentage,
    
    COALESCE(pms.total_sets_won, 0) AS sets_won,
    COALESCE(pms.total_sets_lost, 0) AS sets_lost,
    
    -- Latest Match / Rating details
    p.last_match_date,
    prc.last_rating_change,
    prc.rating_before AS last_match_rating_before,
    prc.rating_after AS last_match_rating_after
FROM player p
CROSS JOIN tier_config tc
LEFT JOIN academy a ON p.primary_academy_id = a.academy_id
LEFT JOIN player_match_stats pms ON p.player_id = pms.player_id
LEFT JOIN player_latest_rating_change prc ON p.player_id = prc.player_id
LEFT JOIN player_first_rating_change pfrc ON p.player_id = pfrc.player_id
ORDER BY p.current_rating DESC;

