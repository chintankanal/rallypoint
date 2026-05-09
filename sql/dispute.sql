-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Dispute Status
DO $$ BEGIN
    CREATE TYPE dispute_status AS ENUM ('OPEN', 'UNDER_REVIEW', 'RESOLVED', 'EXPIRED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create a custom ENUM for Dispute Resolution
DO $$ BEGIN
    CREATE TYPE dispute_resolution AS ENUM ('CONFIRMED_ORIGINAL', 'CORRECTED', 'VOIDED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the Dispute table
CREATE TABLE IF NOT EXISTS dispute (
    dispute_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID REFERENCES match(match_id) NOT NULL,
    raised_by UUID REFERENCES users(user_id) NOT NULL,
    reason TEXT NOT NULL,
    status dispute_status NOT NULL DEFAULT 'OPEN',
    resolution dispute_resolution,
    corrected_sets_won_a INTEGER,
    corrected_sets_won_b INTEGER,
    resolved_by UUID REFERENCES users(user_id),
    resolution_notes TEXT,
    reviewed_by UUID REFERENCES users(user_id),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    resolution_deadline TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_dispute_match_active ON dispute(match_id) WHERE status IN ('OPEN', 'UNDER_REVIEW');
CREATE INDEX IF NOT EXISTS idx_dispute_status_open_review ON dispute(status) WHERE status IN ('OPEN', 'UNDER_REVIEW');
CREATE INDEX IF NOT EXISTS idx_dispute_resolution_deadline_open_review ON dispute(resolution_deadline) WHERE status IN ('OPEN', 'UNDER_REVIEW');