-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the PlayerSeedingHistory table
CREATE TABLE IF NOT EXISTS player_seeding_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID REFERENCES player(player_id) NOT NULL,
    old_seeding_level seeding_level NOT NULL,
    new_seeding_level seeding_level NOT NULL,
    old_seeding_reference VARCHAR(255),
    new_seeding_reference VARCHAR(255),
    correction_reason TEXT NOT NULL,
    corrected_by UUID REFERENCES users(user_id) NOT NULL,
    corrected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rating_adjustment_applied BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_player_seeding_history_player_corrected_at ON player_seeding_history(player_id, corrected_at DESC);