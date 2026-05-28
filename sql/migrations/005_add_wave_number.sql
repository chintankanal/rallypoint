-- Phase 3 of the fixture engine redesign — multi-wave numeric scheduling
-- (docs/fixture_engine_phased_impl_plan.md §3c, critique §11).
--
-- The legacy sub_round VARCHAR(1) "A"/"B" column only modeled 2-wave rounds.
-- This migration adds a numeric wave_number column that supports N waves and
-- updates the per-round uniqueness constraint accordingly. sub_round remains
-- as a legacy display label and is derived from wave_number by the engine.

-- ── fixture_slot (intra-academy sessions) ────────────────────────────────────

ALTER TABLE fixture_slot
    ADD COLUMN IF NOT EXISTS wave_number INT NOT NULL DEFAULT 1;

-- Backfill: any existing rows where sub_round = 'B' belong to wave 2; the rest
-- stay on wave 1 (default). On a pre-launch DB this is a no-op.
UPDATE fixture_slot SET wave_number = 2 WHERE sub_round = 'B';

-- Replace the legacy (session_id, round, sub_round, table) uniqueness with
-- (session_id, round, wave, table). The old constraint is dropped only if it
-- still exists.
DO $$ BEGIN
    ALTER TABLE fixture_slot DROP CONSTRAINT uq_fixture_slot_session_round_table;
EXCEPTION
    WHEN undefined_object THEN null;
END $$;

ALTER TABLE fixture_slot
    ADD CONSTRAINT uq_fixture_slot_session_round_wave_table
    UNIQUE (session_id, round_number, wave_number, table_number);

-- ── event_fixture_slot (inter-academy events) ────────────────────────────────

ALTER TABLE event_fixture_slot
    ADD COLUMN IF NOT EXISTS wave_number INT NOT NULL DEFAULT 1;

DO $$ BEGIN
    ALTER TABLE event_fixture_slot DROP CONSTRAINT uq_event_fixture_slot_round_table;
EXCEPTION
    WHEN undefined_object THEN null;
END $$;

ALTER TABLE event_fixture_slot
    ADD CONSTRAINT uq_event_fixture_slot_round_wave_table
    UNIQUE (event_id, round_number, wave_number, table_number);
