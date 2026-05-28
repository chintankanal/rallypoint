-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Match Category (legacy field — see round_intent /
-- gap_band / player_*_role for the richer per-slot semantics introduced in
-- migrations/004_add_fixture_slot_additive_fields.sql; this is kept as a
-- compatibility field consumed by match_service and player_service).
DO $$ BEGIN
    CREATE TYPE match_category AS ENUM ('COMPETITIVE', 'STRETCH', 'ANCHOR');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Critique §2 additive types — also defined in
-- migrations/004_add_fixture_slot_additive_fields.sql for incremental rollout.
DO $$ BEGIN
    CREATE TYPE round_intent AS ENUM ('COMPETITIVE', 'DEVELOPMENTAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE gap_band AS ENUM ('COMPETITIVE', 'STRETCH', 'OUT_OF_BAND', 'BYE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE player_role AS ENUM ('PEER', 'ANCHORING', 'STRETCHING', 'BYE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create a custom ENUM for Fixture Slot Status
DO $$ BEGIN
    CREATE TYPE fixture_slot_status AS ENUM ('SCHEDULED', 'PLAYED', 'UNPLAYED', 'BYE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the FixtureSlot table
CREATE TABLE IF NOT EXISTS fixture_slot (
    slot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES session(session_id) NOT NULL,
    round_number INTEGER NOT NULL,
    sub_round VARCHAR(1), -- A / B, Nullable. To be superseded by a numeric wave column in Phase 3.
    table_number INTEGER NOT NULL,
    -- Round-level intent and per-slot semantics (critique §2).
    round_intent round_intent NOT NULL DEFAULT 'COMPETITIVE',
    gap_band gap_band NOT NULL DEFAULT 'COMPETITIVE',
    player_a_role player_role NOT NULL DEFAULT 'PEER',
    player_b_role player_role NOT NULL DEFAULT 'BYE',
    -- Legacy compatibility field — derived from gap_band by the engine.
    match_category match_category NOT NULL,
    player_a_id UUID REFERENCES player(player_id) NOT NULL,
    player_b_id UUID REFERENCES player(player_id), -- NULL = BYE
    expected_rating_gap DECIMAL(10, 2) NOT NULL,
    status fixture_slot_status NOT NULL DEFAULT 'SCHEDULED',
    match_id UUID, -- FK to Match, added later to avoid circular dependency
    updated_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_fixture_slot_session_round_table UNIQUE (session_id, round_number, sub_round, table_number)
);

CREATE INDEX IF NOT EXISTS idx_fixture_slot_band ON fixture_slot(gap_band);