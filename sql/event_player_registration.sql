-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Event Player Registration Status
DO $$ BEGIN
    CREATE TYPE registration_status AS ENUM ('REGISTERED', 'CHECKED_IN', 'WITHDRAWN', 'NO_SHOW');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the EventPlayerRegistration table
CREATE TABLE IF NOT EXISTS event_player_registration (
    registration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES event(event_id) NOT NULL,
    player_id UUID REFERENCES player(player_id) NOT NULL,
    registered_by UUID REFERENCES users(user_id) NOT NULL,
    registered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status registration_status NOT NULL DEFAULT 'REGISTERED',
    checked_in_by UUID REFERENCES users(user_id),
    withdrawn_at TIMESTAMP WITH TIME ZONE,
    withdrawn_by UUID REFERENCES users(user_id),

    CONSTRAINT uq_event_player_registration UNIQUE (event_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_event_player_registration_event_status ON event_player_registration(event_id, status);
CREATE INDEX IF NOT EXISTS idx_event_player_registration_player_event ON event_player_registration(player_id, event_id);