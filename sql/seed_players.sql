-- Set the default timezone for this database session to IST
SET timezone TO 'Asia/Kolkata';

-- Seed 5 players with a mix of seeded and unseeded levels for the target academy
-- Target Academy ID: f72a6351-fd4d-401a-be57-1e6b1ad138bf

DO $$
DECLARE
    v_academy_id UUID := 'f72a6351-fd4d-401a-be57-1e6b1ad138bf';
    v_creator_id UUID;
BEGIN
    -- Fetch an existing user (Admin/Coach) to satisfy the created_by/updated_by FK constraints
    SELECT user_id INTO v_creator_id FROM users WHERE role IN ('ADMIN', 'COACH') LIMIT 1;
    
    -- Fallback to any active user if no Admin/Coach found
    IF v_creator_id IS NULL THEN
        SELECT user_id INTO v_creator_id FROM users WHERE is_active = TRUE LIMIT 1;
    END IF;

    IF v_creator_id IS NULL THEN
        RAISE EXCEPTION 'No users found in the database. Please seed at least one user before seeding players.';
    END IF;

    -- Player 1: Unseeded (Default starting rating)
    INSERT INTO player (name, date_of_birth, gender, nationality, primary_academy_id, seeding_level, virtual_matches, current_rating, created_by, updated_by)
    VALUES ('Aarav Sharma', '2012-05-15', 'MALE', 'India', v_academy_id, 'UNSEEDED', 0, 1000.00, v_creator_id, v_creator_id)
    ON CONFLICT DO NOTHING;

    -- Player 2: Unseeded
    INSERT INTO player (name, date_of_birth, gender, nationality, primary_academy_id, seeding_level, virtual_matches, current_rating, created_by, updated_by)
    VALUES ('Ananya Iyer', '2013-08-22', 'FEMALE', 'India', v_academy_id, 'UNSEEDED', 0, 1000.00, v_creator_id, v_creator_id)
    ON CONFLICT DO NOTHING;

    -- Player 3: Seeded (District level - starts with 10 virtual matches)
    INSERT INTO player (name, date_of_birth, gender, nationality, primary_academy_id, seeding_level, seeding_reference, virtual_matches, current_rating, created_by, updated_by)
    VALUES ('Ishaan Patel', '2011-03-10', 'MALE', 'India', v_academy_id, 'DISTRICT', 'DIST-2023-REF-045', 10, 1200.00, v_creator_id, v_creator_id)
    ON CONFLICT DO NOTHING;

    -- Player 4: Seeded (State level - starts with 20 virtual matches)
    INSERT INTO player (name, date_of_birth, gender, nationality, primary_academy_id, seeding_level, seeding_reference, virtual_matches, current_rating, created_by, updated_by)
    VALUES ('Sanya Malhotra', '2010-11-30', 'FEMALE', 'India', v_academy_id, 'STATE', 'STATE-RANK-2024-12', 20, 1400.00, v_creator_id, v_creator_id)
    ON CONFLICT DO NOTHING;

    -- Player 5: Seeded (National level - starts with 30 virtual matches)
    INSERT INTO player (name, date_of_birth, gender, nationality, primary_academy_id, seeding_level, seeding_reference, virtual_matches, current_rating, created_by, updated_by)
    VALUES ('Rohan Dasgupta', '2009-01-05', 'MALE', 'India', v_academy_id, 'NATIONAL', 'NAT-QUAL-REF-001', 30, 1500.00, v_creator_id, v_creator_id)
    ON CONFLICT DO NOTHING;

    RAISE NOTICE 'Successfully seeded 5 players for academy %', v_academy_id;
END $$;