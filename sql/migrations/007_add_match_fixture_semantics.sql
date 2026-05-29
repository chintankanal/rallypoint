-- Add fixture semantic fields to match table for downstream migration
-- These fields are populated at match submission time from fixture_slot / event_fixture_slot

DO $$ BEGIN
    CREATE TYPE gap_band AS ENUM ('COMPETITIVE', 'STRETCH', 'OUT_OF_BAND', 'BYE');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE round_intent AS ENUM ('COMPETITIVE', 'DEVELOPMENTAL');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE player_role AS ENUM ('PEER', 'ANCHORING', 'STRETCHING', 'BYE');
EXCEPTION WHEN duplicate_object THEN null; END $$;

ALTER TABLE match ADD COLUMN IF NOT EXISTS gap_band gap_band;
ALTER TABLE match ADD COLUMN IF NOT EXISTS round_intent round_intent;
ALTER TABLE match ADD COLUMN IF NOT EXISTS player_a_role player_role;
ALTER TABLE match ADD COLUMN IF NOT EXISTS player_b_role player_role;

CREATE INDEX IF NOT EXISTS idx_match_gap_band ON match(gap_band);
CREATE INDEX IF NOT EXISTS idx_match_round_intent ON match(round_intent);
CREATE INDEX IF NOT EXISTS idx_match_player_a_role ON match(player_a_role);
