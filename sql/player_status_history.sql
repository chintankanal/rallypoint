-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the PlayerStatusHistory table
CREATE TABLE IF NOT EXISTS player_status_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID REFERENCES player(player_id) NOT NULL,
    from_status player_status, -- Nullable for initial status
    to_status player_status NOT NULL,
    reason TEXT NOT NULL,
    changed_by UUID REFERENCES users(user_id) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_player_status_history_player_changed_at ON player_status_history(player_id, changed_at DESC);