/*
Transaction-Level Query (Rating & Tier Transitions)
This query retrieves every recorded rating change. It joins the 
rating_history.sql, player.sql, match.sql, and event.sql tables, dynamically identifying the opponent for each transaction.
*/
SELECT 
    -- Rating History details
    rh.history_id,
    rh.created_at AS rating_applied_at,
    rh.rating_before,
    rh.rating_after,
    rh.delta AS rating_change,
    rh.tier_before,
    rh.tier_after,
    rh.expected_score,
    rh.actual_score,
    
    -- Player details
    p.player_id,
    p.name AS player_name,
    p.gender AS player_gender,
    p.date_of_birth AS player_dob,
    p.nationality AS player_nationality,
    p.seeding_level AS player_seeding_level,
    
    -- Opponent details (derived from the match pair)
    opp.player_id AS opponent_id,
    opp.name AS opponent_name,
    opp.gender AS opponent_gender,
    
    -- Match details
    m.match_id,
    m.match_date,
    m.match_timestamp,
    m.sets_won_a,
    m.sets_won_b,
    m.is_retirement,
    CASE 
        WHEN m.winner_id = p.player_id THEN 'WON'
        ELSE 'LOST'
    END AS match_outcome,
    m.confirmation_status,
    
    -- Event details
    e.event_id,
    e.name AS event_name,
    e.event_type,
    e.scheduling_mode,
    e.status AS event_status
FROM rating_history rh
INNER JOIN player p ON rh.player_id = p.player_id
INNER JOIN match m ON rh.match_id = m.match_id
INNER JOIN event e ON m.event_id = e.event_id
LEFT JOIN player opp ON opp.player_id = (
    CASE 
        WHEN rh.player_id = m.player_a_id THEN m.player_b_id 
        ELSE m.player_a_id 
    END
)
ORDER BY rh.created_at DESC;
