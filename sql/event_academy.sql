-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the EventAcademy table
CREATE TABLE IF NOT EXISTS event_academy (
    event_id UUID REFERENCES event(event_id) NOT NULL,
    academy_id UUID REFERENCES academy(academy_id) NOT NULL,
    added_by UUID REFERENCES users(user_id) NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_by UUID REFERENCES users(user_id),
    removed_at TIMESTAMP WITH TIME ZONE,

    PRIMARY KEY (event_id, academy_id)
);

CREATE INDEX IF NOT EXISTS idx_event_academy_event_id ON event_academy(event_id) WHERE removed_at IS NULL;