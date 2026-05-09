-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Tier (reusing from player.sql if it existed, but defining here for safety)
DO $$ BEGIN
    CREATE TYPE tier AS ENUM ('BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'ELITE', 'NATIONAL_TRACK');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the RatingHistory table
CREATE TABLE IF NOT EXISTS rating_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID REFERENCES player(player_id) NOT NULL,
    match_id UUID REFERENCES match(match_id) NOT NULL,
    rating_before DECIMAL(10, 2) NOT NULL,
    rating_after DECIMAL(10, 2) NOT NULL,
    delta DECIMAL(10, 2) NOT NULL,
    delta_breakdown JSONB NOT NULL,
    tier_before tier NOT NULL,
    tier_after tier NOT NULL,
    cr_before DECIMAL(10, 2) NOT NULL,
    cr_after DECIMAL(10, 2) NOT NULL,
    k_base DECIMAL(10, 2) NOT NULL,
    k_eff DECIMAL(10, 2) NOT NULL,
    k_shared DECIMAL(10, 2) NOT NULL,
    expected_score DECIMAL(10, 2) NOT NULL,
    actual_score DECIMAL(10, 2) NOT NULL,
    age_bonus DECIMAL(10, 2) NOT NULL,
    is_rollback BOOLEAN NOT NULL DEFAULT FALSE,
    rollback_of_history_id UUID REFERENCES rating_history(history_id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rating_history_player_created_at ON rating_history(player_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rating_history_match_id ON rating_history(match_id);