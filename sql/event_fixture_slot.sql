-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Reuse match_category and fixture_slot_status ENUMs defined in fixture_slot.sql

CREATE TABLE IF NOT EXISTS event_fixture_slot (
    slot_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES event(event_id) ON DELETE CASCADE,
    round_number        INT NOT NULL,
    table_number        INT NOT NULL DEFAULT 1,
    match_category      match_category NOT NULL,
    player_a_id         UUID NOT NULL REFERENCES player(player_id),
    player_b_id         UUID REFERENCES player(player_id),  -- NULL = BYE
    expected_rating_gap DECIMAL(10,2) NOT NULL DEFAULT 0,
    status              fixture_slot_status NOT NULL DEFAULT 'SCHEDULED',
    match_id            UUID,  -- FK to match added later to avoid circular dependency
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_event_fixture_slot_round_table UNIQUE (event_id, round_number, table_number)
);

CREATE INDEX IF NOT EXISTS idx_event_fixture_slot_event ON event_fixture_slot(event_id, round_number);
