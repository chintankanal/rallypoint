-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Match Category
DO $$ BEGIN
    CREATE TYPE match_category AS ENUM ('COMPETITIVE', 'STRETCH', 'ANCHOR');
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
    sub_round VARCHAR(1), -- A / B, Nullable
    table_number INTEGER NOT NULL,
    match_category match_category NOT NULL,
    player_a_id UUID REFERENCES player(player_id) NOT NULL,
    player_b_id UUID REFERENCES player(player_id) NOT NULL,
    expected_rating_gap DECIMAL(10, 2) NOT NULL,
    status fixture_slot_status NOT NULL DEFAULT 'SCHEDULED',
    match_id UUID, -- FK to Match, added later to avoid circular dependency
    updated_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_fixture_slot_session_round_table UNIQUE (session_id, round_number, sub_round, table_number)
);