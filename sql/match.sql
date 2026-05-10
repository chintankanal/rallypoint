-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Match Confirmation Status (reusing from API contract)
DO $$ BEGIN
    CREATE TYPE confirmation_status AS ENUM ('PENDING', 'CONFIRMED', 'DISPUTED', 'VOIDED', 'AUTO_CONFIRMED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create a custom ENUM for Match Not Eligible Reason
DO $$ BEGIN
    CREATE TYPE not_eligible_reason AS ENUM ('RATING_GAP_EXCEEDED', 'ZERO_SETS_RETIREMENT', 'WALKOVER');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the Match table
CREATE TABLE IF NOT EXISTS match (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES event(event_id) NOT NULL,
    session_id UUID REFERENCES session(session_id),
    fixture_slot_id UUID, -- Can reference fixture_slot(slot_id) or event_fixture_slot(slot_id)
    player_a_id UUID REFERENCES player(player_id) NOT NULL,
    player_b_id UUID REFERENCES player(player_id) NOT NULL,
    player_a_academy_id UUID REFERENCES academy(academy_id) NOT NULL, -- Snapshot
    player_b_academy_id UUID REFERENCES academy(academy_id) NOT NULL, -- Snapshot
    match_format match_format NOT NULL, -- Reusing match_format enum from event.sql
    sets_won_a INTEGER NOT NULL,
    sets_won_b INTEGER NOT NULL,
    sets_won_a_actual INTEGER, -- Nullable, for retirement
    sets_won_b_actual INTEGER, -- Nullable, for retirement
    is_retirement BOOLEAN NOT NULL,
    winner_id UUID REFERENCES player(player_id) NOT NULL,
    rating_eligible BOOLEAN NOT NULL,
    not_eligible_reason not_eligible_reason,
    ratings_applied_at TIMESTAMP WITH TIME ZONE,
    diminishing_signal_applied BOOLEAN NOT NULL DEFAULT FALSE,
    match_category match_category, -- Reusing match_category enum from fixture_slot.sql, Nullable if not from fixture
    match_date DATE NOT NULL,
    match_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    umpire_id UUID REFERENCES users(user_id),
    submitted_by UUID REFERENCES users(user_id) NOT NULL,
    confirmed_by UUID REFERENCES users(user_id),
    confirmation_status confirmation_status NOT NULL DEFAULT 'PENDING',
    confirmation_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    confirmed_at TIMESTAMP WITH TIME ZONE,
    voided_at TIMESTAMP WITH TIME ZONE,
    voided_by UUID REFERENCES users(user_id),
    void_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_match_player_order CHECK (player_a_id < player_b_id), -- Canonical ordering
    CONSTRAINT chk_match_rating_eligible_reason CHECK (
        NOT (rating_eligible = FALSE AND not_eligible_reason IS NULL)
    ),
    CONSTRAINT chk_match_ratings_applied_eligible CHECK (
        NOT (ratings_applied_at IS NOT NULL AND rating_eligible = FALSE)
    )
);

-- Dedup for ad-hoc matches (no session): same pair cannot play twice in same event on same day
CREATE UNIQUE INDEX IF NOT EXISTS uq_match_ad_hoc ON match (player_a_id, player_b_id, event_id, match_date) WHERE session_id IS NULL;
-- Dedup for fixture-slot matches: one match per slot
CREATE UNIQUE INDEX IF NOT EXISTS uq_match_fixture_slot ON match (fixture_slot_id) WHERE fixture_slot_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_match_players_date_desc ON match(player_a_id, player_b_id, match_date DESC);
CREATE INDEX IF NOT EXISTS idx_match_player_b_confirmation_status ON match(player_b_id, confirmation_status) WHERE confirmation_status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_match_event_date ON match(event_id, match_date);
CREATE INDEX IF NOT EXISTS idx_match_date_confirmation_status ON match(match_date, confirmation_status) WHERE confirmation_status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_match_date_rating_eligible_applied ON match(match_date, rating_eligible, ratings_applied_at);
CREATE INDEX IF NOT EXISTS idx_match_event_rating_eligible_applied ON match(event_id, rating_eligible, ratings_applied_at);
CREATE INDEX IF NOT EXISTS idx_match_confirmation_deadline_pending ON match(confirmation_deadline) WHERE confirmation_status = 'PENDING';

-- Add FK to fixture_slot.match_id after match table is created
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_fixture_slot_match') THEN
        ALTER TABLE fixture_slot
        ADD CONSTRAINT fk_fixture_slot_match
        FOREIGN KEY (match_id) REFERENCES match(match_id);
    END IF;
END $$;