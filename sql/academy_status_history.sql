-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Status Triggered By (used by multiple history tables)
DO $$ BEGIN
    CREATE TYPE status_triggered_by AS ENUM ('SYSTEM', 'ADMIN', 'REFEREE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the AcademyStatusHistory table
CREATE TABLE IF NOT EXISTS academy_status_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    academy_id UUID REFERENCES academy(academy_id) NOT NULL,
    from_status academy_status, -- from_status can be null for initial status
    to_status academy_status NOT NULL,
    reason TEXT, -- Required for INACTIVE
    triggered_by status_triggered_by NOT NULL,
    changed_by UUID REFERENCES users(user_id), -- Nullable if SYSTEM triggered
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_academy_status_history_academy_changed_at ON academy_status_history(academy_id, changed_at DESC);