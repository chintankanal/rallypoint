-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Identifier Type
DO $$ BEGIN
    CREATE TYPE identifier_type AS ENUM ('EMAIL', 'PHONE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the UserIdentifierHistory table
CREATE TABLE IF NOT EXISTS user_identifier_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) NOT NULL,
    type identifier_type NOT NULL,
    old_value VARCHAR(255) NOT NULL,
    new_value VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID REFERENCES users(user_id) NOT NULL,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_id_hist_user_id ON user_identifier_history(user_id);