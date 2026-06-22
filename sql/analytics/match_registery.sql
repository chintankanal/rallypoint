/*
This query displays all played matches, referencing their respective events and player rosters.
*/
SELECT 
    m.match_id,
    m.match_date,
    m.match_timestamp,
    e.name AS event_name,
    e.event_type,
    e.scheduling_mode,
    
    -- Player A
    pa.player_id AS player_a_id,
    pa.name AS player_a_name,
    m.sets_won_a AS player_a_sets_won,
    
    -- Player B
    pb.player_id AS player_b_id,
    pb.name AS player_b_name,
    m.sets_won_b AS player_b_sets_won,
    
    -- Winner
    w.player_id AS winner_id,
    w.name AS winner_name,
    
    -- Eligibility & Status
    m.is_retirement,
    m.rating_eligible,
    m.not_eligible_reason,
    m.confirmation_status,
    m.confirmed_at
FROM match m
INNER JOIN event e ON m.event_id = e.event_id
INNER JOIN player pa ON m.player_a_id = pa.player_id
INNER JOIN player pb ON m.player_b_id = pb.player_id
INNER JOIN player w ON m.winner_id = w.player_id
ORDER BY m.match_timestamp DESC;
