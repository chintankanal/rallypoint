-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create the match_set_score table
CREATE TABLE IF NOT EXISTS match_set_score (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    set_number INTEGER NOT NULL,  -- 1, 2, 3, etc.
    points_a INTEGER NOT NULL,
    points_b INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_set_number_positive CHECK (set_number > 0),
    CONSTRAINT chk_points_nonnegative CHECK (points_a >= 0 AND points_b >= 0),
    UNIQUE (match_id, set_number)
);

CREATE INDEX IF NOT EXISTS idx_match_set_score_match_id ON match_set_score(match_id);