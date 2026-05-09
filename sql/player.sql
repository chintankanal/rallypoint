-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create custom ENUMs for Player
DO $$ BEGIN
    CREATE TYPE seeding_level AS ENUM ('UNSEEDED', 'DISTRICT', 'STATE', 'NATIONAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE player_status AS ENUM ('ACTIVE', 'INACTIVE', 'SUSPENDED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the Player table
CREATE TABLE IF NOT EXISTS player (
    player_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(user_id), -- Optional link to app account
    name VARCHAR(255) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender gender,
    nationality VARCHAR(100) NOT NULL DEFAULT 'India',
    seeding_level seeding_level NOT NULL DEFAULT 'UNSEEDED',
    seeding_reference VARCHAR(255),
    virtual_matches INTEGER NOT NULL DEFAULT 0,
    current_rating DECIMAL(10, 2) NOT NULL DEFAULT 1000.00,
    rated_matches_completed INTEGER NOT NULL DEFAULT 0,
    last_match_date DATE,
    primary_academy_id UUID NOT NULL REFERENCES academy(academy_id),
    last_academy_change_date DATE,
    guardian_name VARCHAR(255),
    guardian_phone VARCHAR(50),
    contact_email VARCHAR(255),
    status player_status NOT NULL DEFAULT 'ACTIVE',
    created_by UUID NOT NULL REFERENCES users(user_id),
    updated_by UUID NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Leaderboards and Analytics defined in docs
CREATE INDEX IF NOT EXISTS idx_player_rating ON player (status, current_rating DESC);
CREATE INDEX IF NOT EXISTS idx_player_academy_rating ON player (primary_academy_id, status, current_rating DESC);
CREATE INDEX IF NOT EXISTS idx_player_dob_rating ON player (date_of_birth, status, current_rating DESC);
CREATE INDEX IF NOT EXISTS idx_player_gender ON player (gender) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_player_inactivity ON player (last_match_date) WHERE status = 'ACTIVE';

-- Constraint: seeding_reference required when seeding_level is not UNSEEDED
DO $$ BEGIN
    ALTER TABLE player ADD CONSTRAINT check_seeding_reference 
    CHECK (seeding_level = 'UNSEEDED' OR seeding_reference IS NOT NULL);
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;