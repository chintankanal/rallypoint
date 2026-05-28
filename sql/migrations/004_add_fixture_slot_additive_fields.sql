-- Phase 2 of the fixture engine redesign (docs/fixture_engine_phased_impl_plan.md).
-- Adds the additive slot model from critique §2 to both intra-academy
-- (fixture_slot) and inter-academy (event_fixture_slot) tables.
--
-- The legacy match_category column stays in place as a compatibility field
-- consumed by match_service.py and player_service.py. Downstream consumers
-- will migrate to the richer fields in a follow-on phase.

-- ── New ENUM types ───────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE round_intent AS ENUM ('COMPETITIVE', 'DEVELOPMENTAL');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE gap_band AS ENUM ('COMPETITIVE', 'STRETCH', 'OUT_OF_BAND', 'BYE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE player_role AS ENUM ('PEER', 'ANCHORING', 'STRETCHING', 'BYE');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ── fixture_slot (intra-academy sessions) ────────────────────────────────────

ALTER TABLE fixture_slot
    ADD COLUMN IF NOT EXISTS round_intent  round_intent NOT NULL DEFAULT 'COMPETITIVE',
    ADD COLUMN IF NOT EXISTS gap_band      gap_band     NOT NULL DEFAULT 'COMPETITIVE',
    ADD COLUMN IF NOT EXISTS player_a_role player_role  NOT NULL DEFAULT 'PEER',
    ADD COLUMN IF NOT EXISTS player_b_role player_role  NOT NULL DEFAULT 'BYE';

-- ── event_fixture_slot (inter-academy events) ────────────────────────────────

ALTER TABLE event_fixture_slot
    ADD COLUMN IF NOT EXISTS round_intent  round_intent NOT NULL DEFAULT 'COMPETITIVE',
    ADD COLUMN IF NOT EXISTS gap_band      gap_band     NOT NULL DEFAULT 'COMPETITIVE',
    ADD COLUMN IF NOT EXISTS player_a_role player_role  NOT NULL DEFAULT 'PEER',
    ADD COLUMN IF NOT EXISTS player_b_role player_role  NOT NULL DEFAULT 'BYE';

-- Indexes for analytic filtering on intent/band (cheap; tables are small).
CREATE INDEX IF NOT EXISTS idx_fixture_slot_band       ON fixture_slot(gap_band);
CREATE INDEX IF NOT EXISTS idx_event_fixture_slot_band ON event_fixture_slot(gap_band);
