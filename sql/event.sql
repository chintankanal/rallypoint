-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Create custom ENUMs for Event
DO $$ BEGIN
    CREATE TYPE scheduling_mode AS ENUM ('INTRA_ACADEMY', 'INTER_ACADEMY');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE event_type AS ENUM ('LEAGUE', 'FRIENDLY', 'TOURNAMENT_EXTERNAL', 'TOURNAMENT_MANAGED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE match_format AS ENUM ('BEST_OF_3', 'BEST_OF_5', 'BEST_OF_7');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE tournament_format AS ENUM ('SWISS', 'TIER_BANDED_KNOCKOUT', 'GROUP_THEN_KNOCKOUT');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE event_status AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create the Event table
CREATE TABLE IF NOT EXISTS event (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season_id UUID REFERENCES season(season_id),
    name VARCHAR(255) NOT NULL,
    event_type event_type NOT NULL,
    scheduling_mode scheduling_mode NOT NULL,
    default_match_format match_format,
    tournament_format tournament_format,
    host_academy_id UUID REFERENCES academy(academy_id),
    start_date DATE NOT NULL,
    end_date DATE,
    status event_status NOT NULL DEFAULT 'SCHEDULED',
    created_by UUID REFERENCES users(user_id) NOT NULL,
    updated_by UUID REFERENCES users(user_id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_event_name UNIQUE (name),
    CONSTRAINT chk_event_scheduling_mode_type CHECK (
        NOT (scheduling_mode = 'INTRA_ACADEMY' AND event_type = 'LEAGUE') AND
        NOT (scheduling_mode = 'INTRA_ACADEMY' AND event_type = 'TOURNAMENT_EXTERNAL') AND
        NOT (scheduling_mode = 'INTRA_ACADEMY' AND event_type = 'TOURNAMENT_MANAGED') AND
        NOT (scheduling_mode = 'INTER_ACADEMY' AND event_type = 'FRIENDLY')
    )
);

CREATE INDEX IF NOT EXISTS idx_event_status_start_date ON event(status, start_date);
CREATE INDEX IF NOT EXISTS idx_event_host_academy ON event(host_academy_id);