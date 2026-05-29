-- Backfill match table with fixture semantics from fixture slot references
-- Historical matches without fixture_slot references use a conservative fallback.

UPDATE match m
SET 
    gap_band = COALESCE(m.gap_band, fs.gap_band),
    round_intent = COALESCE(m.round_intent, fs.round_intent),
    player_a_role = COALESCE(m.player_a_role, fs.player_a_role),
    player_b_role = COALESCE(m.player_b_role, fs.player_b_role)
FROM fixture_slot fs
WHERE m.fixture_slot_id = fs.slot_id
  AND m.gap_band IS NULL;

UPDATE match m
SET 
    gap_band = COALESCE(m.gap_band, efs.gap_band),
    round_intent = COALESCE(m.round_intent, efs.round_intent),
    player_a_role = COALESCE(m.player_a_role, efs.player_a_role),
    player_b_role = COALESCE(m.player_b_role, efs.player_b_role)
FROM event_fixture_slot efs
WHERE m.fixture_slot_id = efs.slot_id
  AND m.gap_band IS NULL;

UPDATE match
SET 
    gap_band = CASE 
        WHEN match_category = 'COMPETITIVE' THEN 'COMPETITIVE'::gap_band
        WHEN match_category = 'STRETCH' THEN 'STRETCH'::gap_band
        ELSE 'COMPETITIVE'::gap_band
    END,
    round_intent = 'COMPETITIVE'::round_intent,
    player_a_role = 'PEER'::player_role,
    player_b_role = 'PEER'::player_role
WHERE gap_band IS NULL AND match_category IS NOT NULL;

UPDATE match
SET 
    gap_band = COALESCE(gap_band, 'COMPETITIVE'::gap_band),
    round_intent = COALESCE(round_intent, 'COMPETITIVE'::round_intent),
    player_a_role = COALESCE(player_a_role, 'PEER'::player_role),
    player_b_role = COALESCE(player_b_role, 'PEER'::player_role)
WHERE gap_band IS NULL;
