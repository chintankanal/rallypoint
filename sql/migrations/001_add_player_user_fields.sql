-- Migration 001: Add gender to users + player; add player profile fields
-- Run once against the existing database. Safe to re-run (uses IF NOT EXISTS / IF EXISTS guards).

SET timezone TO 'Asia/Kolkata';

-- ── Gender enum ───────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE gender AS ENUM ('MALE', 'FEMALE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ── users table ───────────────────────────────────────────────────────────────

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS gender gender;

-- ── player table ─────────────────────────────────────────────────────────────

ALTER TABLE player
    ADD COLUMN IF NOT EXISTS gender gender,
    ADD COLUMN IF NOT EXISTS guardian_name  VARCHAR(255),
    ADD COLUMN IF NOT EXISTS guardian_phone VARCHAR(50),
    ADD COLUMN IF NOT EXISTS contact_email  VARCHAR(255),
    ADD COLUMN IF NOT EXISTS nationality    VARCHAR(100) NOT NULL DEFAULT 'India';

-- Fix the misleading DDL default (code always supplies the value explicitly,
-- but this keeps the schema honest for direct SQL inserts / seed scripts).
ALTER TABLE player
    ALTER COLUMN current_rating SET DEFAULT 1000.00;

-- ── Indexes for new columns ───────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_player_gender ON player (gender) WHERE status = 'ACTIVE';
