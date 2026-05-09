-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create a custom ENUM for Academy ASI Calculation Basis
DO $$ BEGIN
    CREATE TYPE asi_calculation_basis AS ENUM ('COMPUTED', 'FROZEN', 'DEFAULTED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the AcademyASIHistory table
CREATE TABLE IF NOT EXISTS academy_asi_history (
    history_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    academy_id UUID REFERENCES academy(academy_id) NOT NULL,
    asi_value DECIMAL(10, 2), -- Nullable if <5 players
    qualifying_player_count INTEGER NOT NULL,
    calculation_basis asi_calculation_basis NOT NULL,
    global_average_at_calculation DECIMAL(10, 2) NOT NULL,
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_academy_asi_history_academy_calculated_at ON academy_asi_history(academy_id, calculated_at DESC);