# Fixture Engine v2: Code-Level Change Specification

## I. Database Schema Changes

### 1.1 Migration: Add match table columns

**File**: `sql/migrations/005_add_fixture_semantics_to_match.sql`

```sql
-- Add fixture semantic fields to match table for Phase 8 downstream migration
-- These fields are populated at match submission time from fixture_slot / event_fixture_slot

-- Create types if not already present (should be from fixture_slot.sql)
DO $$ BEGIN
    CREATE TYPE gap_band AS ENUM ('COMPETITIVE', 'STRETCH', 'OUT_OF_BAND', 'BYE');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE round_intent AS ENUM ('COMPETITIVE', 'DEVELOPMENTAL');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE player_role AS ENUM ('PEER', 'ANCHORING', 'STRETCHING', 'BYE');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- Add columns to match table
ALTER TABLE match ADD COLUMN IF NOT EXISTS gap_band gap_band;
ALTER TABLE match ADD COLUMN IF NOT EXISTS round_intent round_intent;
ALTER TABLE match ADD COLUMN IF NOT EXISTS player_a_role player_role;
ALTER TABLE match ADD COLUMN IF NOT EXISTS player_b_role player_role;

-- Create indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_match_gap_band ON match(gap_band);
CREATE INDEX IF NOT EXISTS idx_match_round_intent ON match(round_intent);
CREATE INDEX IF NOT EXISTS idx_match_player_a_role ON match(player_a_role);
```

### 1.2 Migration: Backfill existing matches

**File**: `sql/migrations/006_backfill_match_fixture_semantics.sql`

```sql
-- Backfill match table with fixture semantics from fixture_slot references
-- For matches that have a fixture_slot_id, populate fields from the slot.
-- For matches without fixture_slot_id, use defaults.

-- INTRA_ACADEMY matches (have session_id, reference fixture_slot)
UPDATE match m
SET 
    gap_band = COALESCE(m.gap_band, fs.gap_band),
    round_intent = COALESCE(m.round_intent, fs.round_intent),
    player_a_role = COALESCE(m.player_a_role, fs.player_a_role),
    player_b_role = COALESCE(m.player_b_role, fs.player_b_role)
FROM fixture_slot fs
WHERE m.fixture_slot_id = fs.slot_id
  AND m.gap_band IS NULL;

-- INTER_ACADEMY matches (have event_id, reference event_fixture_slot)
UPDATE match m
SET 
    gap_band = COALESCE(m.gap_band, efs.gap_band),
    round_intent = COALESCE(m.round_intent, efs.round_intent),
    player_a_role = COALESCE(m.player_a_role, efs.player_a_role),
    player_b_role = COALESCE(m.player_b_role, efs.player_b_role)
FROM event_fixture_slot efs
WHERE m.fixture_slot_id = efs.slot_id
  AND m.gap_band IS NULL;

-- For historical matches without fixture_slot_id, derive from match_category if present
UPDATE match
SET 
    gap_band = CASE 
        WHEN match_category = 'COMPETITIVE' THEN 'COMPETITIVE'::gap_band
        WHEN match_category = 'STRETCH' THEN 'STRETCH'::gap_band
        ELSE 'COMPETITIVE'::gap_band
    END,
    round_intent = 'COMPETITIVE'::round_intent,
    player_a_role = 'PEER'::player_role,
    player_b_role = 'PEER'::player_role
WHERE gap_band IS NULL AND match_category IS NOT NULL;

-- Set defaults for any remaining nulls
UPDATE match
SET 
    gap_band = COALESCE(gap_band, 'COMPETITIVE'::gap_band),
    round_intent = COALESCE(round_intent, 'COMPETITIVE'::round_intent),
    player_a_role = COALESCE(player_a_role, 'PEER'::player_role),
    player_b_role = COALESCE(player_b_role, 'PEER'::player_role)
WHERE gap_band IS NULL;
```

---

## II. Backend Service Changes

### 2.1 match_service.py — Full Refactor

**File**: `app/services/match_service.py`

#### Change 1: Extract fixture fields (Lines 195-211)

**BEFORE**:
```python
        # Validate fixture slot if provided
        slot_match_category = None
        is_event_slot = event["scheduling_mode"] == "INTER_ACADEMY"
        if body.fixture_slot_id:
            slot_table = "event_fixture_slot" if is_event_slot else "fixture_slot"
            cur.execute(
                f"SELECT slot_id::text, player_a_id::text, player_b_id::text, status, match_category "
                f"FROM {slot_table} WHERE slot_id = %s",
                (body.fixture_slot_id,),
            )
            slot = cur.fetchone()
            if not slot:
                raise ValueError("Fixture slot not found")
            if slot["status"] != "SCHEDULED":
                raise ValueError(f"Fixture slot is already '{slot['status']}'")
            if slot["player_a_id"] != a_id or slot["player_b_id"] != b_id:
                raise ValueError("Fixture slot players do not match the submitted players")
            slot_match_category = slot["match_category"]
```

**AFTER**:
```python
        # Validate fixture slot if provided
        slot_match_category = None
        slot_gap_band = None
        slot_round_intent = None
        slot_player_a_role = None
        slot_player_b_role = None
        is_event_slot = event["scheduling_mode"] == "INTER_ACADEMY"
        if body.fixture_slot_id:
            slot_table = "event_fixture_slot" if is_event_slot else "fixture_slot"
            cur.execute(
                f"SELECT slot_id::text, player_a_id::text, player_b_id::text, status, "
                f"       match_category, gap_band, round_intent, player_a_role, player_b_role "
                f"FROM {slot_table} WHERE slot_id = %s",
                (body.fixture_slot_id,),
            )
            slot = cur.fetchone()
            if not slot:
                raise ValueError("Fixture slot not found")
            if slot["status"] != "SCHEDULED":
                raise ValueError(f"Fixture slot is already '{slot['status']}'")
            if slot["player_a_id"] != a_id or slot["player_b_id"] != b_id:
                raise ValueError("Fixture slot players do not match the submitted players")
            slot_match_category = slot["match_category"]
            slot_gap_band = slot["gap_band"]
            slot_round_intent = slot["round_intent"]
            slot_player_a_role = slot["player_a_role"]
            slot_player_b_role = slot["player_b_role"]
```

#### Change 2: Insert new fields (Lines 237-267)

**BEFORE**:
```python
        cur.execute(
            """
            INSERT INTO match (
                match_id, event_id, session_id, fixture_slot_id,
                player_a_id, player_b_id,
                player_a_academy_id, player_b_academy_id,
                match_format,
                sets_won_a, sets_won_b,
                sets_won_a_actual, sets_won_b_actual,
                is_retirement, winner_id,
                rating_eligible, not_eligible_reason,
                diminishing_signal_applied,
                match_date, match_timestamp,
                submitted_by, confirmation_status, confirmed_by, confirmed_at,
                confirmation_deadline,
                match_category
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s, %s, %s, %s,
                %s,
                %s
            )
            """,
            (
                match_id, body.event_id, body.session_id, body.fixture_slot_id,
                a_id, b_id,
                a_academy, b_academy,
                match_format,
                sets_a, sets_b,
                sets_a_act, sets_b_act,
                body.is_retirement, winner_id,
                rating_eligible, not_eligible_reason,
                diminishing,
                body.match_date, now_utc,
                submitted_by_user_id, confirmation_status, confirmed_by, confirmed_at,
                deadline_utc,
                slot_match_category,
            ),
        )
```

**AFTER**:
```python
        cur.execute(
            """
            INSERT INTO match (
                match_id, event_id, session_id, fixture_slot_id,
                player_a_id, player_b_id,
                player_a_academy_id, player_b_academy_id,
                match_format,
                sets_won_a, sets_won_b,
                sets_won_a_actual, sets_won_b_actual,
                is_retirement, winner_id,
                rating_eligible, not_eligible_reason,
                diminishing_signal_applied,
                match_date, match_timestamp,
                submitted_by, confirmation_status, confirmed_by, confirmed_at,
                confirmation_deadline,
                match_category, gap_band, round_intent, player_a_role, player_b_role
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s, %s, %s
            )
            """,
            (
                match_id, body.event_id, body.session_id, body.fixture_slot_id,
                a_id, b_id,
                a_academy, b_academy,
                match_format,
                sets_a, sets_b,
                sets_a_act, sets_b_act,
                body.is_retirement, winner_id,
                rating_eligible, not_eligible_reason,
                diminishing,
                body.match_date, now_utc,
                submitted_by_user_id, confirmation_status, confirmed_by, confirmed_at,
                deadline_utc,
                slot_match_category, slot_gap_band, slot_round_intent,
                slot_player_a_role, slot_player_b_role,
            ),
        )
```

#### Change 3: Use gap_band for rating eligibility (NEW METHOD)

**ADD** new function to match_service.py:
```python
def _check_gap_band_eligibility(
    gap_band: str | None,
    player_a_rating: float,
    player_b_rating: float,
) -> tuple[bool, str | None]:
    """
    Determine if match is rating-eligible based on gap_band from fixture.
    
    - COMPETITIVE / STRETCH: Rating gap must be ≤ 500 (strict rating cap)
    - OUT_OF_BAND: Should not be rating-eligible (constraint from fixture engine)
    - BYE: Always not rating-eligible (no opponent)
    
    Falls back to raw rating cap check if gap_band not provided (legacy matches).
    """
    gap_cap = 500  # Hard cap enforced by rating services (see critique §2c)
    
    if gap_band == "BYE":
        return False, "BYE_NO_OPPONENT"
    
    if gap_band == "OUT_OF_BAND":
        # OUT_OF_BAND slots should not appear in normal fixture generation,
        # but if they do, they're not eligible (see Phase 2 constraint).
        if abs(player_a_rating - player_b_rating) > gap_cap:
            return False, "OUT_OF_BAND_EXCEEDS_CAP"
        # If within cap despite labeling, allow but log concern
        return True, None
    
    # COMPETITIVE, STRETCH, or None (legacy)
    if abs(player_a_rating - player_b_rating) > gap_cap:
        return False, "RATING_GAP_EXCEEDED"
    
    return True, None
```

**UPDATE** `_check_eligibility()` to use gap_band when available:
```python
def _check_eligibility(
    player_a_rating: float,
    player_b_rating: float,
    sets_won_a: int,
    sets_won_b: int,
    is_retirement: bool,
    match_format: str,
    gap_band: str | None = None,  # NEW parameter
) -> tuple[bool, str | None]:
    """
    Returns (rating_eligible, not_eligible_reason | None).
    Evaluated at submission time using raw current ratings.
    """
    required = _REQUIRED_WINNER_SETS.get(match_format, 0)

    # Walkover: 0-0 and NOT retirement
    if sets_won_a == 0 and sets_won_b == 0 and not is_retirement:
        return False, "WALKOVER"

    # Retirement with zero physical sets played
    if is_retirement and sets_won_a == 0 and sets_won_b == 0:
        return False, "ZERO_SETS_RETIREMENT"

    # Use gap_band for rating eligibility if provided; fallback to raw check
    if gap_band is not None:
        eligible, reason = _check_gap_band_eligibility(gap_band, player_a_rating, player_b_rating)
        if not eligible:
            return eligible, reason
    else:
        # Legacy: raw rating gap check
        if abs(player_a_rating - player_b_rating) > 500:
            return False, "RATING_GAP_EXCEEDED"

    return True, None
```

**UPDATE** call to `_check_eligibility()` in `submit_match()`:
```python
        # Check eligibility (with fixture context)
        rating_eligible, not_eligible_reason = _check_eligibility(
            player_a["current_rating"],
            player_b["current_rating"],
            sets_a, sets_b,
            body.is_retirement,
            match_format,
            gap_band=slot_gap_band,  # NEW
        )
```

---

### 2.2 player_service.py — Add Role Exposure Tracking

**File**: `app/services/player_service.py`

**ADD** new function:
```python
def get_player_role_exposure(
    conn,
    player_id: str,
    period_days: int = 90,
) -> dict[str, int]:
    """
    Calculate player's exposure to different roles over a period.
    
    Returns:
        {
            'as_peer': count of matches where player was PEER,
            'as_anchoring': count where player was ANCHORING,
            'as_stretching': count where player was STRETCHING,
            'bye_count': count of BYEs,
            'total_rounds': total fixture slots (including BYEs),
        }
    """
    from datetime import date, timedelta
    
    cutoff_date = date.today() - timedelta(days=period_days)
    
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                COUNT(*) FILTER (WHERE player_a_role = 'PEER' OR player_b_role = 'PEER') AS peer_count,
                COUNT(*) FILTER (WHERE player_a_role = 'ANCHORING' OR player_b_role = 'ANCHORING') AS anchoring_count,
                COUNT(*) FILTER (WHERE player_a_role = 'STRETCHING' OR player_b_role = 'STRETCHING') AS stretching_count,
                COUNT(*) FILTER (WHERE player_a_role = 'BYE' OR player_b_role = 'BYE') AS bye_count,
                COUNT(*) AS total_count
            FROM match
            WHERE (player_a_id = %s OR player_b_id = %s)
              AND match_date >= %s
              AND confirmation_status NOT IN ('VOIDED')
            """,
            (player_id, player_id, cutoff_date),
        )
        row = cur.fetchone()
    
    return {
        'as_peer': int(row['peer_count']) if row else 0,
        'as_anchoring': int(row['anchoring_count']) if row else 0,
        'as_stretching': int(row['stretching_count']) if row else 0,
        'bye_count': int(row['bye_count']) if row else 0,
        'total_rounds': int(row['total_count']) if row else 0,
    }
```

**EXTEND** ComputedStats schema in routers (if using computed-stats endpoint):
```python
# In schemas/player.py or where ComputedStats is defined, add:
class PlayerRoleExposure(BaseModel):
    as_peer: int
    as_anchoring: int
    as_stretching: int
    bye_count: int
    total_rounds: int

class ComputedStats(BaseModel):
    player_id: str
    tier: str
    confidence_ratio: float
    is_provisional: bool
    provisional_matches_remaining: int
    weeks_inactive: int | None
    age_as_of_jan1: int
    age_group: str
    total_matches: int
    inactivity_decay_active: bool
    # NEW:
    role_exposure: PlayerRoleExposure  # 90-day window
```

**UPDATE** endpoint to include role exposure:
```python
# In app/routers/players.py or wherever GET /players/{id}/computed-stats is:
@router.get("/{player_id}/computed-stats", response_model=ComputedStats)
def get_player_stats(player_id: str, _: dict = _ANY):
    with get_connection() as conn:
        # ... existing code ...
        
        role_exposure = player_service.get_player_role_exposure(conn, player_id)
        
        return ComputedStats(
            player_id=player_id,
            # ... existing fields ...
            role_exposure=role_exposure,
        )
```

---

### 2.3 analytics.py — Gap Band Migration

**File**: `app/routers/analytics.py`

#### Change 1: Replace match_category with gap_band (Lines 49-50)

**BEFORE**:
```python
                    COUNT(*) FILTER (WHERE m.match_category = 'STRETCH') AS stretch_matches,
                    COUNT(*) FILTER (WHERE m.match_category = 'STRETCH'
                                      AND m.winner_id::text = rh.player_id::text) AS stretch_wins,
```

**AFTER**:
```python
                    COUNT(*) FILTER (WHERE m.gap_band = 'STRETCH') AS stretch_matches,
                    COUNT(*) FILTER (WHERE m.gap_band = 'STRETCH'
                                      AND m.winner_id::text = rh.player_id::text) AS stretch_wins,
```

#### Change 2: Add role and gap_band breakdowns

**BEFORE** (return statement around line 80):
```python
    return VelocityReport(
        player_id=player_id,
        period=period,
        start_rating=start_r,
        end_rating=end_r,
        rating_change=round(rating_change, 2),
        matches_played=mp,
        wins=wins,
        win_rate=round(win_rate, 4),
        stretch_matches=stretch_matches,
        stretch_wins=stretch_wins,
        stretch_win_rate=round(stretch_win_rate, 4) if stretch_win_rate is not None else None,
        tier_changes=tier_changes,
    )
```

**AFTER**:
```python
    # Compute role and gap_band breakdowns
    cur.execute(
        """
        SELECT 
            player_a_role,
            COUNT(*) as matches,
            COUNT(*) FILTER (WHERE winner_id::text = rh.player_id::text) as wins
        FROM rating_history rh
        JOIN match m ON m.match_id = rh.match_id
        WHERE rh.player_id = %s AND rh.is_rollback = FALSE
          AND m.match_date >= %s
        GROUP BY player_a_role
        UNION ALL
        SELECT 
            player_b_role,
            COUNT(*) as matches,
            COUNT(*) FILTER (WHERE winner_id::text = rh.player_id::text) as wins
        FROM rating_history rh
        JOIN match m ON m.match_id = rh.match_id
        WHERE rh.player_id = %s AND rh.is_rollback = FALSE
          AND m.match_date >= %s
        GROUP BY player_b_role
        """,
        (player_id, since, player_id, since),
    )
    role_breakdown = {}
    for row in cur.fetchall():
        role = row['player_a_role']
        if role not in role_breakdown:
            role_breakdown[role] = {'wins': 0, 'total': 0}
        role_breakdown[role]['total'] += int(row['matches'])
        role_breakdown[role]['wins'] += int(row['wins'])
    
    cur.execute(
        """
        SELECT 
            gap_band,
            COUNT(*) as matches,
            COUNT(*) FILTER (WHERE winner_id::text = rh.player_id::text) as wins
        FROM rating_history rh
        JOIN match m ON m.match_id = rh.match_id
        WHERE rh.player_id = %s AND rh.is_rollback = FALSE
          AND m.match_date >= %s
        GROUP BY gap_band
        """,
        (player_id, since),
    )
    gap_band_breakdown = {}
    for row in cur.fetchall():
        band = row['gap_band']
        if band not in gap_band_breakdown:
            gap_band_breakdown[band] = {'wins': 0, 'total': 0}
        gap_band_breakdown[band]['total'] += int(row['matches'])
        gap_band_breakdown[band]['wins'] += int(row['wins'])
    
    return VelocityReport(
        player_id=player_id,
        period=period,
        start_rating=start_r,
        end_rating=end_r,
        rating_change=round(rating_change, 2),
        matches_played=mp,
        wins=wins,
        win_rate=round(win_rate, 4),
        stretch_matches=stretch_matches,
        stretch_wins=stretch_wins,
        stretch_win_rate=round(stretch_win_rate, 4) if stretch_win_rate is not None else None,
        tier_changes=tier_changes,
        role_breakdown=role_breakdown,  # NEW
        gap_band_breakdown=gap_band_breakdown,  # NEW
    )
```

**UPDATE** VelocityReport schema to include optional breakdown fields:
```python
# In schemas/leaderboard.py or where VelocityReport is defined:

class VelocityReport(BaseModel):
    player_id: str
    period: str
    start_rating: float | None
    end_rating: float | None
    rating_change: float
    matches_played: int
    wins: int
    win_rate: float
    stretch_matches: int
    stretch_wins: int
    stretch_win_rate: float | None
    tier_changes: int
    # NEW optional fields:
    role_breakdown: dict[str, dict[str, int]] | None = None
    gap_band_breakdown: dict[str, dict[str, int]] | None = None
```

---

### 2.4 event_service.py — Fixture Quality Endpoint

**File**: `app/services/event_service.py`

**ADD** new function:
```python
def get_fixture_quality_report(conn, event_id: str) -> dict:
    """
    Returns comprehensive fixture semantics and quality metrics.
    
    {
        'event_id': str,
        'total_slots': int,
        'by_gap_band': {'COMPETITIVE': int, 'STRETCH': int, 'OUT_OF_BAND': int, 'BYE': int},
        'by_round_intent': {'COMPETITIVE': int, 'DEVELOPMENTAL': int},
        'role_distribution': {'PEER': int, 'ANCHORING': int, 'STRETCHING': int, 'BYE': int},
        'cross_academy_pct': float,
    }
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                COUNT(*) as total_slots,
                COUNT(*) FILTER (WHERE gap_band = 'COMPETITIVE') as competitive_slots,
                COUNT(*) FILTER (WHERE gap_band = 'STRETCH') as stretch_slots,
                COUNT(*) FILTER (WHERE gap_band = 'OUT_OF_BAND') as out_of_band_slots,
                COUNT(*) FILTER (WHERE gap_band = 'BYE') as bye_slots,
                COUNT(*) FILTER (WHERE round_intent = 'COMPETITIVE') as competitive_rounds,
                COUNT(*) FILTER (WHERE round_intent = 'DEVELOPMENTAL') as developmental_rounds,
                COUNT(*) FILTER (WHERE player_a_role = 'PEER' OR player_b_role = 'PEER') as peer_count,
                COUNT(*) FILTER (WHERE player_a_role = 'ANCHORING' OR player_b_role = 'ANCHORING') as anchoring_count,
                COUNT(*) FILTER (WHERE player_a_role = 'STRETCHING' OR player_b_role = 'STRETCHING') as stretching_count,
                COUNT(*) FILTER (WHERE gap_band = 'BYE') as bye_count,
                COUNT(*) FILTER (WHERE player_a_id IS NOT NULL AND player_b_id IS NOT NULL 
                                      AND pa.primary_academy_id != pb.primary_academy_id) as cross_academy_matches,
                COUNT(*) FILTER (WHERE player_a_id IS NOT NULL AND player_b_id IS NOT NULL) as total_matches
            FROM event_fixture_slot efs
            LEFT JOIN player pa ON pa.player_id = efs.player_a_id
            LEFT JOIN player pb ON pb.player_id = efs.player_b_id
            WHERE efs.event_id = %s
            """,
            (event_id,),
        )
        row = dict(cur.fetchone())
    
    total_slots = int(row['total_slots'])
    total_matches = int(row['total_matches']) or 1  # avoid division by zero
    
    cross_academy_pct = (int(row['cross_academy_matches']) / total_matches * 100) if total_matches > 0 else 0
    
    return {
        'event_id': event_id,
        'total_slots': total_slots,
        'by_gap_band': {
            'COMPETITIVE': int(row['competitive_slots']),
            'STRETCH': int(row['stretch_slots']),
            'OUT_OF_BAND': int(row['out_of_band_slots']),
            'BYE': int(row['bye_slots']),
        },
        'by_round_intent': {
            'COMPETITIVE': int(row['competitive_rounds']),
            'DEVELOPMENTAL': int(row['developmental_rounds']),
        },
        'role_distribution': {
            'PEER': int(row['peer_count']),
            'ANCHORING': int(row['anchoring_count']),
            'STRETCHING': int(row['stretching_count']),
            'BYE': int(row['bye_count']),
        },
        'cross_academy_pct': round(cross_academy_pct, 2),
    }
```

**ADD** router endpoint:
```python
# In app/routers/events.py or create app/routers/fixture_analytics.py:

@router.get("/{event_id}/fixture-quality-report")
def get_event_fixture_quality(event_id: str, _: dict = _ANY):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT event_id FROM event WHERE event_id = %s", (event_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Event not found")
        
        report = event_service.get_fixture_quality_report(conn, event_id)
    
    return report
```

---

## III. Frontend Changes

### 3.1 EventDetailPanel.tsx — Fixture Display Enhancement

**File**: `web/src/components/EventDetailPanel.tsx`

#### Change 1: New function to create match metadata from explicit fields

**ADD** after line 30 (after existing utility functions):
```typescript
interface MatchTypeMeta {
  label: string
  shortLabel: string
  title: string
  className: string
  badgeColor?: string
}

/**
 * Build match type metadata from explicit fixture semantics.
 * Preferred over getMatchTypeMeta() which infers from ratings.
 */
function getMatchMetaFromFixtureSlot(
  slot: EventFixtureSlot,
  playerIsA: boolean,
): MatchTypeMeta {
  const playerRole = playerIsA ? slot.player_a_role : slot.player_b_role
  const gapBand = slot.gap_band

  // Map (gap_band, role) → display metadata
  if (gapBand === 'COMPETITIVE' && playerRole === 'PEER') {
    return {
      label: 'Competitive',
      shortLabel: 'C',
      title: 'Competitive: matched skill level',
      className: 'text-blue-300',
      badgeColor: 'bg-blue-900/40 border-blue-700/50',
    }
  }

  if (gapBand === 'STRETCH') {
    if (playerRole === 'STRETCHING') {
      return {
        label: 'Stretch Up',
        shortLabel: 'S↑',
        title: 'Stretch: playing up against stronger opponent',
        className: 'text-purple-300',
        badgeColor: 'bg-purple-900/40 border-purple-700/50',
      }
    }
    if (playerRole === 'ANCHORING') {
      return {
        label: 'Anchor Down',
        shortLabel: 'A↓',
        title: 'Anchor: playing down as stronger opponent',
        className: 'text-amber-300',
        badgeColor: 'bg-amber-900/40 border-amber-700/50',
      }
    }
  }

  if (gapBand === 'OUT_OF_BAND') {
    return {
      label: 'Exception',
      shortLabel: 'E',
      title: 'Exception: outside normal range (≤500 gap cap)',
      className: 'text-red-400',
      badgeColor: 'bg-red-900/40 border-red-700/50',
    }
  }

  if (gapBand === 'BYE') {
    return {
      label: 'Bye',
      shortLabel: 'B',
      title: 'Bye: no opponent this round',
      className: 'text-gray-500',
      badgeColor: 'bg-gray-800/40 border-gray-700/50',
    }
  }

  // Fallback (shouldn't reach here if gap_band is valid)
  return {
    label: gapBand || 'Unknown',
    shortLabel: (gapBand || 'U')[0],
    title: `Match type: ${gapBand}`,
    className: 'text-gray-400',
  }
}
```

#### Change 2: Update fixture rendering loop

**BEFORE** (fixture slot rendering, currently not visible in excerpt but used around line 355+):
```typescript
// Pseudo-code showing current pattern
slots.map(slot => (
  <div key={slot.slot_id} className="...">
    <span>{getMatchTypeMeta(slot.match_category, ...?).label}</span>
    {/* other fields */}
  </div>
))
```

**AFTER**:
```typescript
slots.map(slot => {
  const playerIsA = slot.player_a.player_id === playerIdBeingViewed
  const meta = getMatchMetaFromFixtureSlot(slot, playerIsA)
  const opponent = playerIsA ? slot.player_b : slot.player_a

  return (
    <div key={slot.slot_id} className={`border rounded-lg p-3 space-y-1.5 ${meta.badgeColor || 'bg-gray-800/30 border-gray-700/50'}`}>
      {/* Round and wave info */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-400">Round {slot.round_number}, Wave {slot.wave_number}</span>
        <span className={`font-semibold ${meta.className}`}>
          {meta.shortLabel}
        </span>
      </div>

      {/* Match type badge and intent */}
      <div className="flex items-center gap-2 flex-wrap">
        <span title={meta.title} className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${meta.className}`}>
          {meta.label}
        </span>
        <span className="text-xs text-gray-500">
          {slot.round_intent === 'DEVELOPMENTAL' ? '(Developmental)' : ''}
        </span>
      </div>

      {/* Opponent info */}
      {opponent ? (
        <div className="bg-gray-800/50 rounded px-2 py-1.5 space-y-0.5">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-white">
              vs {getOpponentLabel(opponent, firstNameCounts)}
            </span>
            <span className="text-xs text-gray-500">{Math.round(opponent.current_rating)}</span>
          </div>
          <div className="text-xs text-gray-400">
            {opponent.academy_name}
          </div>
          <div className="text-xs text-gray-500">
            Table {slot.table_number} | Expected gap: ±{slot.expected_rating_gap}
          </div>
        </div>
      ) : (
        <div className="bg-gray-800/50 rounded px-2 py-1.5">
          <span className="text-sm text-gray-400">Bye (no opponent)</span>
        </div>
      )}

      {/* Role indicator (show what role this player has) */}
      <div className="text-xs text-gray-500">
        Your role: <span className="font-semibold text-gray-300">{playerIsA ? slot.player_a_role : slot.player_b_role}</span>
      </div>

      {/* Match status */}
      <div className="flex items-center justify-between pt-1 border-t border-gray-700">
        <span className="text-xs text-gray-500">
          Status: <span className={`font-medium ${slot.status === 'PLAYED' ? 'text-green-400' : 'text-yellow-400'}`}>
            {slot.status}
          </span>
        </span>
        {slot.match_id && (
          <a href={`/matches/${slot.match_id}`} className="text-xs text-blue-400 hover:underline">
            View Result →
          </a>
        )}
      </div>
    </div>
  )
})
```

---

### 3.2 MatchDetail.tsx — Add Fixture Context

**File**: `web/src/components/MatchDetail.tsx`

**ADD** fixture slot display section (after existing match result section):
```typescript
import { useQuery } from '@tanstack/react-query'
import { eventsApi } from '../api/client'

export function MatchDetail({ matchId }: { matchId: string }) {
  // ... existing code ...
  
  const matchQ = useQuery(...)  // existing
  const fixtureQ = useQuery(
    ['fixture-slot', matchData?.fixture_slot_id],
    () => eventsApi.getFixtures(matchData.event_id),  // or new specific endpoint
    { enabled: !!matchData?.fixture_slot_id }
  )

  return (
    <div className="space-y-6">
      {/* Existing match result section */}
      {/* ... */}

      {/* NEW: Fixture Context Section */}
      {fixtureQ.data && (
        <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-300">Fixture Context</h3>
          
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-gray-500">Round:</span>
              <span className="ml-2 text-gray-300">#{fixtureQ.data.round_number}</span>
            </div>
            <div>
              <span className="text-gray-500">Wave:</span>
              <span className="ml-2 text-gray-300">{fixtureQ.data.wave_number}</span>
            </div>
            <div>
              <span className="text-gray-500">Gap Band:</span>
              <span className="ml-2 font-medium text-blue-300">{fixtureQ.data.gap_band}</span>
            </div>
            <div>
              <span className="text-gray-500">Round Intent:</span>
              <span className="ml-2 text-gray-300">{fixtureQ.data.round_intent}</span>
            </div>
            <div>
              <span className="text-gray-500">Your Role:</span>
              <span className="ml-2 font-medium text-amber-300">
                {matchData.player_a_id === playerIdBeingViewed ? fixtureQ.data.player_a_role : fixtureQ.data.player_b_role}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Expected Gap:</span>
              <span className="ml-2 text-gray-300">±{fixtureQ.data.expected_rating_gap}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

---

## IV. Type Updates (Already Done)

**File**: `web/src/api/client.ts`

✅ EventFixtureSlot type already includes:
```typescript
round_intent: string
gap_band: string
player_a_role: string
player_b_role: string
```

No changes needed.

---

## V. Testing Specifications

### Unit Tests: match_service.py

**File**: `tests/unit/test_match_service_migration.py`

```python
def test_match_stores_fixture_semantics():
    """Verify match row captures gap_band, round_intent, and roles from fixture_slot."""
    # Submit match with fixture_slot_id
    # Assert gap_band, round_intent, player_a_role, player_b_role stored in match table
    pass

def test_gap_band_eligibility_competitive():
    """COMPETITIVE gap_band should allow gaps ≤ 500."""
    pass

def test_gap_band_eligibility_bye():
    """BYE gap_band should not be rating-eligible."""
    pass

def test_gap_band_eligibility_out_of_band():
    """OUT_OF_BAND should not be rating-eligible."""
    pass

def test_match_without_fixture_slot_uses_defaults():
    """Legacy matches without fixture_slot_id should use default semantics."""
    pass
```

### Integration Tests

**File**: `tests/integration/test_fixture_migration_e2e.py`

```python
def test_event_fixture_to_match_flow():
    """Full flow: generate fixtures → submit match → verify all semantics stored."""
    # 1. Generate event fixtures (engine outputs new fields)
    # 2. Submit match against fixture slot
    # 3. Query match table
    # 4. Assert gap_band, round_intent, roles all present and correct
    pass

def test_analytics_velocity_report_with_gap_band():
    """Velocity report should filter on gap_band instead of match_category."""
    # 1. Submit several matches with different gap_bands
    # 2. Call velocity endpoint
    # 3. Verify stretch_matches count matches gap_band='STRETCH' count
    # 4. Verify role_breakdown and gap_band_breakdown present
    pass

def test_fixture_quality_report():
    """Fixture quality endpoint should return valid breakdown."""
    # 1. Generate event fixtures
    # 2. Call fixture-quality-report endpoint
    # 3. Assert all counts sum correctly
    pass
```

---

## VI. Migration Checklist

- [ ] Create migration: 005_add_fixture_semantics_to_match.sql
- [ ] Create migration: 006_backfill_match_fixture_semantics.sql
- [ ] Update match_service.py (3 changes: SELECT, INSERT, _check_eligibility)
- [ ] Add player_service.py role exposure tracking
- [ ] Update analytics.py (gap_band filter + breakdowns)
- [ ] Add event_service.py fixture quality endpoint
- [ ] Update EventDetailPanel.tsx (new function + render)
- [ ] Update MatchDetail.tsx (add fixture context)
- [ ] Update schemas/leaderboard.py (VelocityReport fields)
- [ ] Add all unit tests (match_service)
- [ ] Add all integration tests (full flow)
- [ ] Run full test suite (expect 0 regressions)
- [ ] Update API documentation (deprecation note for match_category)
- [ ] Create fixture_semantics_migration.md guide

