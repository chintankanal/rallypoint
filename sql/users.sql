SET timezone TO 'Asia/Kolkata';

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('PLAYER', 'COACH', 'ADMIN', 'REFEREE', 'UMPIRE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE gender AS ENUM ('MALE', 'FEMALE', 'OTHER');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255), /* Nullable to support passwordless/OTP login */
    phone VARCHAR(50),
    role user_role NOT NULL,
    gender gender,
    academy_id UUID, /* Foreign Key added in academy.sql */
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_by UUID REFERENCES users(user_id),
    deactivated_by UUID REFERENCES users(user_id),
    deactivated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_user_email UNIQUE (email),
    CONSTRAINT uq_user_phone UNIQUE (phone),
    CONSTRAINT check_coach_has_academy CHECK (role != 'COACH' OR academy_id IS NOT NULL),
    CONSTRAINT check_deactivation_consistency CHECK (
        (deactivated_by IS NULL AND deactivated_at IS NULL) OR
        (deactivated_by IS NOT NULL AND deactivated_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_user_email ON users(email);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_phone') THEN
        ALTER TABLE users ADD CONSTRAINT uq_user_phone UNIQUE (phone);
    END IF;
END $$;
