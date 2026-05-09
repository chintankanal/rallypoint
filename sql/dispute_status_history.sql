-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the DisputeStatusHistory table
CREATE TABLE IF NOT EXISTS dispute_status_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispute_id UUID REFERENCES dispute(dispute_id) NOT NULL,
    from_status dispute_status,
    to_status dispute_status NOT NULL,
    changed_by UUID REFERENCES users(user_id), -- Nullable if SYSTEM triggered
    triggered_by status_triggered_by NOT NULL, -- Reusing status_triggered_by enum
    notes TEXT,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dispute_status_history_dispute_changed_at ON dispute_status_history(dispute_id, changed_at DESC);