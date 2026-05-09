-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Player Academy Change Reason
DO $$ BEGIN
    CREATE TYPE player_academy_change_reason AS ENUM ('INITIAL_REGISTRATION', 'TRANSFER', 'CORRECTION');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the PlayerAcademyHistory table
CREATE TABLE IF NOT EXISTS player_academy_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID REFERENCES player(player_id) NOT NULL,
    academy_id UUID REFERENCES academy(academy_id) NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE, -- Nullable for current academy
    change_reason player_academy_change_reason NOT NULL,
    changed_by UUID REFERENCES users(user_id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_player_academy_effective_from UNIQUE (player_id, effective_from)
);

CREATE INDEX IF NOT EXISTS idx_player_academy_history_player_effective_to ON player_academy_history(player_id) WHERE effective_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_player_academy_history_player_effective_range ON player_academy_history(player_id, effective_from, effective_to);