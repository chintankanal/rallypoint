-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Academy Status
DO $$ BEGIN
    CREATE TYPE academy_status AS ENUM ('ACTIVE', 'FROZEN', 'INACTIVE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the Academy table
CREATE TABLE IF NOT EXISTS academy (
    academy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    status academy_status NOT NULL DEFAULT 'ACTIVE',
    frozen_since DATE,
    min_tables INTEGER NOT NULL DEFAULT 1,
    created_by UUID NOT NULL REFERENCES users(user_id),
    updated_by UUID NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Now that the academy table exists, link the user table's academy_id
-- We use a check to ensure we don't try to add the same constraint twice
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_academy') THEN
        ALTER TABLE users 
        ADD CONSTRAINT fk_user_academy 
        FOREIGN KEY (academy_id) REFERENCES academy(academy_id);
    END IF;
END $$;

-- Index for performance on city/state lookups
CREATE INDEX IF NOT EXISTS idx_academy_location ON academy(city, state);