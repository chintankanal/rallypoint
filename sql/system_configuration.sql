-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the SystemConfiguration table
CREATE TABLE IF NOT EXISTS system_configuration (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT NOT NULL,
    updated_by UUID REFERENCES users(user_id),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);