-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Bootstrap Phase
DO $$ BEGIN
    CREATE TYPE bootstrap_phase AS ENUM ('DISCOVERY', 'TRANSITION', 'STANDARD');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create a custom ENUM for Session Status (reusing event_status for consistency if applicable, but data model implies separate)
DO $$ BEGIN
    CREATE TYPE session_status AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the Session table
CREATE TABLE IF NOT EXISTS session (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES event(event_id) NOT NULL,
    session_date DATE NOT NULL,
    session_minutes INTEGER NOT NULL,
    num_tables INTEGER NOT NULL,
    match_format match_format NOT NULL, -- Reusing match_format enum from event.sql
    bootstrap_phase bootstrap_phase NOT NULL,
    rating_spread DECIMAL(10, 2) NOT NULL,
    matches_per_player INTEGER NOT NULL,
    present_player_count INTEGER NOT NULL,
    status session_status NOT NULL DEFAULT 'SCHEDULED',
    generated_at TIMESTAMP WITH TIME ZONE,
    generated_by UUID REFERENCES users(user_id),
    created_by UUID REFERENCES users(user_id) NOT NULL,
    updated_by UUID REFERENCES users(user_id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_session_event_date UNIQUE (event_id, session_date)
);