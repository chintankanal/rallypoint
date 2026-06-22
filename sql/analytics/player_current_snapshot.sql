/*
This query returns all players, their current rating, and their primary academy. It dynamically calculates the player's current Tier using the system configuration thresholds (falling back to standard system defaults if config rows are missing).
*/
WITH tier_config AS (
    SELECT 
        COALESCE(MAX(CASE WHEN key = 'tier_beginner_max' THEN value::decimal END), 899.0) AS beginner_max,
        COALESCE(MAX(CASE WHEN key = 'tier_intermediate_max' THEN value::decimal END), 1099.0) AS intermediate_max,
        COALESCE(MAX(CASE WHEN key = 'tier_advanced_max' THEN value::decimal END), 1299.0) AS advanced_max,
        COALESCE(MAX(CASE WHEN key = 'tier_elite_max' THEN value::decimal END), 1499.0) AS elite_max
    FROM system_configuration
)
SELECT 
    p.player_id,
    p.name AS player_name,
    p.date_of_birth,
    p.gender,
    p.nationality,
    p.status AS player_status,
    p.seeding_level,
    p.current_rating,
    p.rated_matches_completed,
    p.virtual_matches,
    p.last_match_date,
    a.name AS primary_academy_name,
    a.city AS academy_city,
    a.state AS academy_state,
    
    -- Dynamic Tier calculation matching get_tier() rules
    CASE 
        WHEN p.current_rating <= tc.beginner_max THEN 'BEGINNER'
        WHEN p.current_rating <= tc.intermediate_max THEN 'INTERMEDIATE'
        WHEN p.current_rating <= tc.advanced_max THEN 'ADVANCED'
        WHEN p.current_rating <= tc.elite_max THEN 'ELITE'
        ELSE 'NATIONAL_TRACK'
    END AS current_tier
FROM player p
CROSS JOIN tier_config tc
LEFT JOIN academy a ON p.primary_academy_id = a.academy_id
ORDER BY p.current_rating DESC;
