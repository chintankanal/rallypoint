-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the EventReferee table
CREATE TABLE IF NOT EXISTS event_referee (
    assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES event(event_id) NOT NULL,
    user_id UUID REFERENCES users(user_id) NOT NULL,
    assigned_by UUID REFERENCES users(user_id) NOT NULL,
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_uq_event_referee_active ON event_referee(event_id, user_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_event_referee_event_id ON event_referee(event_id) WHERE revoked_at IS NULL;