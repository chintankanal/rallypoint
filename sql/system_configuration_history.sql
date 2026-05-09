-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the SystemConfigurationHistory table
CREATE TABLE IF NOT EXISTS system_configuration_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(255) NOT NULL,
    old_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    changed_by UUID REFERENCES users(user_id) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_for_matches_after TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_system_config_history_key ON system_configuration_history(key, changed_at DESC);