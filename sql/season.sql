-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Season Status
DO $$ BEGIN
    CREATE TYPE season_status AS ENUM ('UPCOMING', 'ACTIVE', 'COMPLETED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the Season table
CREATE TABLE IF NOT EXISTS season (
    season_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status season_status NOT NULL DEFAULT 'UPCOMING',
    created_by UUID REFERENCES users(user_id) NOT NULL,
    updated_by UUID REFERENCES users(user_id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_season_name UNIQUE (name)
);