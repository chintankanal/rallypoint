# Fixture Engine v2 Downstream Migration Plan

**Date:** May 29, 2026  
**Status:** COMPREHENSIVE PLAN (Ready for Implementation)  
**Scope:** Service layer, analytics, and frontend updates to consume new fixture semantics

---

## Executive Summary

The fixture engine has been updated (Phase 1-7 of phased_impl_plan.md) to output richer semantic fields:
- `round_intent`: `COMPETITIVE` | `DEVELOPMENTAL` (round-level strategy)
- `gap_band`: `COMPETITIVE` | `STRETCH` | `OUT_OF_BAND` | `BYE` (per-slot fairness band)
- `player_a_role`: `PEER` | `ANCHORING` | `STRETCHING` | `BYE` (player position in matchup)
- `player_b_role`: Same as above

The legacy `match_category: COMPETITIVE | STRETCH | ANCHOR` field is maintained for backward compatibility but should be deprecated after downstream migration.

This document outlines all required changes across the backend services, analytics layer, and frontend.

---

## I. Current State Analysis

### Database Schema (Already Updated)

**fixture_slot** (INTRA_ACADEMY):
```sql
round_intent round_intent NOT NULL DEFAULT 'COMPETITIVE',
gap_band gap_band NOT NULL DEFAULT 'COMPETITIVE',
player_a_role player_role NOT NULL DEFAULT 'PEER',
player_b_role player_role NOT NULL DEFAULT 'BYE',
match_category match_category NOT NULL,  -- legacy
```

**event_fixture_slot** (INTER_ACADEMY):
```sql
round_intent, gap_band, player_a_role, player_b_role  -- all present
match_category  -- legacy field still stored
```

### API Types (Already Updated)

**web/src/api/client.ts - EventFixtureSlot**:
```typescript
export interface EventFixtureSlot {
  round_intent: string
  gap_band: string
  player_a_role: string
  player_b_role: string
  match_category: string  // legacy
  // ... other fields
}
```

### Service Layer (Requires Updates)

1. **match_service.py**
   - Line 195-211: Currently reads `match_category` from fixture slot
   - Should migrate to `gap_band` for more precise semantics
   - Rating eligibility checks should use `gap_band` not `match_category`

2. **player_service.py**
   - No direct fixture field consumption found
   - But `_get_seeding_defaults()` and player stats should account for role-based exposure

3. **leaderboard_service.py**
   - Currently aggregates by `match_category`
   - Should provide dual reporting (legacy + new semantics)

4. **analytics.py**
   - Line 49-50: Velocity report filters on `match_category = 'STRETCH'`
   - Should migrate to `gap_band = 'STRETCH'` and add role breakdowns

### Frontend (Partial Updates Required)

1. **EventDetailPanel.tsx**
   - Currently displays fixtures with `getMatchTypeMeta(category)`
   - Function uses only legacy `match_category`
   - Should incorporate `round_intent`, `gap_band`, and roles

2. **MatchDetail.tsx**
   - No fixture slot fields rendered (only match results)
   - Should display rich metadata if available

---

## II. Detailed Migration Plan

### Phase 1: Core Services Migration (High Priority)

#### 1.1. match_service.py — Fixture Slot Field Migration

**Current behavior** (lines 195-211):
```python
slot_match_category = None
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
    # ... validation ...
    slot_match_category = slot["match_category"]
```

**Required changes**:
1. Expand SELECT to include new fields:
   ```python
   SELECT slot_id::text, player_a_id::text, player_b_id::text, status,
          match_category, gap_band, round_intent, player_a_role, player_b_role
   ```

2. Store all fields in match table (migration needed):
   ```python
   ALTER TABLE match ADD COLUMN gap_band gap_band;
   ALTER TABLE match ADD COLUMN round_intent round_intent;
   ALTER TABLE match ADD COLUMN player_a_role player_role;
   ALTER TABLE match ADD COLUMN player_b_role player_role;
   ```

3. Insert all fields when creating match:
   ```python
   INSERT INTO match (
       ... existing fields ...
       match_category, gap_band, round_intent, player_a_role, player_b_role
   ) VALUES (
       ... existing values ...
       slot_match_category, slot_gap_band, slot_round_intent,
       slot_player_a_role, slot_player_b_role
   )
   ```

**Impact**: Match records retain rich fixture semantics; queries can filter/report on gap_band directly.

---

#### 1.2. player_service.py — Role-Based Exposure Tracking

**Current state**: No direct role tracking in player stats.

**Required additions**:
1. Add computed stats for player exposure by role:
   ```python
   def get_player_role_exposure(conn, player_id: str, period_days: int = 90) -> dict:
       """
       Returns: {
           'as_peer': count,
           'as_anchoring': count,
           'as_stretching': count,
           'bye_count': count,
       }
       """
       # Query match table for gap_band and player_*_role
       # Count wins and losses by role
       # Return exposure metrics
   ```

2. Integrate into existing `player_stats` endpoint:
   - Add `role_exposure` dict to ComputedStats response
   - Include in dashboard displays

**Impact**: Coaches can see role-specific match distribution; players understand their position in fixtures.

---

#### 1.3. leaderboard_service.py — Dual Reporting

**Current behavior**: Reports by match_category (if consumed anywhere).

**Required changes**:
1. Add method to retrieve gap_band-based stats:
   ```python
   def get_match_breakdown_by_gap_band(conn, player_id: str, period_days: int = 90):
       """
       Returns: {
           'competitive': {'wins': int, 'losses': int, 'total': int},
           'stretch': {'wins': int, 'losses': int, 'total': int},
           'out_of_band': {'wins': int, 'losses': int, 'total': int},
       }
       """
   ```

2. Integrate into player profile / velocity report if appropriate.

---

### Phase 2: Reporting & Analytics (Medium Priority)

#### 2.1. analytics.py — Velocity Report Enhancements

**Current implementation** (lines 49-50):
```python
COUNT(*) FILTER (WHERE m.match_category = 'STRETCH') AS stretch_matches,
COUNT(*) FILTER (WHERE m.match_category = 'STRETCH' AND m.winner_id::text = rh.player_id::text) AS stretch_wins,
```

**Required migration**:
1. Replace with gap_band-based query:
   ```python
   COUNT(*) FILTER (WHERE m.gap_band = 'STRETCH') AS stretch_matches,
   COUNT(*) FILTER (WHERE m.gap_band = 'STRETCH' AND m.winner_id::text = rh.player_id::text) AS stretch_wins,
   ```

2. Add role-based breakdowns to VelocityReport:
   ```typescript
   export interface VelocityReport {
       // ... existing fields ...
       role_breakdown?: {
           as_peer: { wins: number; total: number }
           as_anchoring: { wins: number; total: number }
           as_stretching: { wins: number; total: number }
       }
       gap_band_breakdown?: {
           competitive: { wins: number; total: number }
           stretch: { wins: number; total: number }
           out_of_band: { wins: number; total: number }
       }
   }
   ```

3. Extend backend query to calculate these breakdowns.

---

#### 2.2. event_service.py — Fixture Quality Metrics

**New endpoint** (POST /events/{event_id}/fixture-quality-report):
```python
def get_fixture_quality_report(event_id: str):
    """
    Returns: {
        'event_id': str,
        'total_slots': int,
        'by_gap_band': {
            'competitive': int,
            'stretch': int,
            'out_of_band': int,
            'bye': int,
        },
        'by_round_intent': {
            'competitive': int,
            'developmental': int,
        },
        'role_distribution': {
            'peer': int,
            'anchoring': int,
            'stretching': int,
        },
        'cross_academy_pct': float,
        'player_exposure_balance': {...},  # how evenly roles/gaps distributed
    }
    """
```

---

### Phase 3: Frontend Display (High Priority for UX)

#### 3.1. EventDetailPanel.tsx — Fixture Matrix Rendering

**Current behavior** (line 46-62):
```typescript
function getMatchTypeMeta(category: string, playerRating: number, opponentRating?: number) {
  if (category === 'COMPETITIVE') {
    return { label: 'Competitive', shortLabel: 'C', ... }
  }
  if (category === 'ANCHOR') {
    return { label: 'Anchor', shortLabel: 'A', ... }
  }
  if (category === 'STRETCH') {
    // Infers role from rating comparison
  }
  // ...
}
```

**Problem**: Infers roles from ratings instead of using explicit `player_a_role`/`player_b_role`.

**Required changes**:
1. New function to build match type metadata from explicit fields:
   ```typescript
   function getMatchMetaFromFixtureSlot(
     slot: EventFixtureSlot,
     playerRating: number,
     isPlayerA: boolean
   ): MatchTypeMeta {
     const playerRole = isPlayerA ? slot.player_a_role : slot.player_b_role
     const opponentRole = isPlayerA ? slot.player_b_role : slot.player_a_role

     // Map (gap_band, role) → display metadata
     if (slot.gap_band === 'COMPETITIVE' && playerRole === 'PEER') {
       return { label: 'Competitive', color: 'text-blue-300', ... }
     }
     if (slot.gap_band === 'STRETCH' && playerRole === 'STRETCHING') {
       return { label: 'Stretch Up', color: 'text-purple-300', ... }
     }
     if (slot.gap_band === 'STRETCH' && playerRole === 'ANCHORING') {
       return { label: 'Anchor Down', color: 'text-amber-300', ... }
     }
     if (slot.gap_band === 'OUT_OF_BAND') {
       return { label: 'Exception', color: 'text-red-400', ... }
     }
     if (slot.gap_band === 'BYE') {
       return { label: 'Bye', color: 'text-gray-500', ... }
     }
   }
   ```

2. Integrate into fixture slot rendering loop (line 355+):
   ```typescript
   slots.map(slot => {
       const playerIsA = slot.player_a.player_id === playerIdBeingViewed
       const meta = getMatchMetaFromFixtureSlot(slot, playerRating, playerIsA)
       const opponentSlot = playerIsA ? slot.player_b : slot.player_a
       
       // Render with:
       // - gap_band badge (COMPETITIVE | STRETCH | OUT_OF_BAND | BYE)
       // - round_intent label (COMPETITIVE | DEVELOPMENTAL)
       // - role indicator (your role: PEER / ANCHORING / STRETCHING)
   })
   ```

3. New fixture slot card layout:
   ```
   [Round N, Wave M] COMPETITIVE (round_intent)
   ┌──────────────────────────────────┐
   │ STRETCH | Anchor Down (gap_band + role)
   │ vs Opponent (rating, academy)
   │ Table 3
   └──────────────────────────────────┘
   ```

---

#### 3.2. MatchDetail.tsx — Rich Match Metadata

**Current state**: Shows match result but not source fixture semantics.

**Required additions**:
1. Fetch fixture slot data when rendering match:
   ```typescript
   const matchQ = useQuery(...)
   const fixtureQ = useQuery(
       ['fixture-slot', matchData.fixture_slot_id],
       () => getFixtureSlot(matchData.fixture_slot_id)  // NEW endpoint
   )
   ```

2. Display fixture context in match detail:
   ```typescript
   <div className="space-y-2">
       <div>Match Type: {fixtureSlot.gap_band} ({fixtureSlot.player_a_role} vs {fixtureSlot.player_b_role})</div>
       <div>Round Intent: {fixtureSlot.round_intent}</div>
       <div>Expected Gap: {fixtureSlot.expected_rating_gap}</div>
   </div>
   ```

---

#### 3.3. Fixture Slot Type Refinements

**Already in web/src/api/client.ts** (EventFixtureSlot):
```typescript
round_intent: string
gap_band: string
player_a_role: string
player_b_role: string
match_category: string  // legacy
```

**No changes needed** — types already support new fields.

---

### Phase 4: Historical Data & Migration (Lower Priority)

#### 4.1. Backfill fixture_slot for INTRA_ACADEMY Sessions

**Problem**: Existing session fixtures may not have new fields populated.

**Solution**:
```sql
-- Migration script: backfill_fixture_slot_new_fields.sql
UPDATE fixture_slot
SET 
    round_intent = COALESCE(round_intent, 'COMPETITIVE'),
    gap_band = CASE 
        WHEN match_category = 'COMPETITIVE' THEN 'COMPETITIVE'
        WHEN match_category = 'STRETCH' THEN 'STRETCH'
        WHEN match_category = 'ANCHOR' THEN 'STRETCH'  -- approximate
        ELSE 'COMPETITIVE'
    END,
    player_a_role = CASE
        WHEN match_category = 'ANCHOR' THEN 'ANCHORING'
        ELSE 'PEER'
    END,
    player_b_role = CASE
        WHEN match_category = 'ANCHOR' THEN 'STRETCHING'
        ELSE 'PEER'
    END
WHERE round_intent IS NULL OR gap_band IS NULL;
```

**Note**: This is approximate mapping from legacy field; precise historical role semantics cannot be recovered.

---

#### 4.2. match_category Deprecation (Phase 7 of engine plan)

**Timeline**: Only after all services and frontend fully migrated.

**Actions**:
1. Add deprecation warning in API docs
2. Provide migration guide for external API consumers
3. Set removal target date (e.g., 2026-Q3)
4. Monitor for breakage via logs

---

## III. Implementation Roadmap

### Week 1: Services Core

| Task | File | Effort | Owner |
|------|------|--------|-------|
| Add match table columns for gap_band, round_intent, roles | sql/migrations/XXX_match_fixture_fields.sql | 0.5h | DB |
| Update match_service.py SELECT and INSERT | app/services/match_service.py | 2h | Backend |
| Add role exposure tracking to player_service | app/services/player_service.py | 1.5h | Backend |
| Create unit tests for new fields | tests/unit/test_match_service_migration.py | 1.5h | QA |
| **Subtotal Week 1** | | **5.5h** | |

### Week 2: Analytics

| Task | File | Effort | Owner |
|------|------|--------|-------|
| Migrate analytics.py to gap_band | app/routers/analytics.py | 1h | Backend |
| Add role breakdowns to velocity report | app/routers/analytics.py | 1.5h | Backend |
| New event_service fixture quality endpoint | app/services/event_service.py | 2h | Backend |
| Tests for analytics migrations | tests/integration/test_analytics_migration.py | 1h | QA |
| **Subtotal Week 2** | | **5.5h** | |

### Week 3: Frontend Display

| Task | File | Effort | Owner |
|------|------|--------|-------|
| Implement getMatchMetaFromFixtureSlot | web/src/components/EventDetailPanel.tsx | 1.5h | Frontend |
| Update fixture slot rendering loop | web/src/components/EventDetailPanel.tsx | 1.5h | Frontend |
| Add fixture quality report UI | web/src/pages/EventDetail.tsx | 2h | Frontend |
| New MatchDetail.tsx fixture context | web/src/components/MatchDetail.tsx | 1.5h | Frontend |
| Type refinements and tests | web/src/types/match.ts | 1h | Frontend |
| **Subtotal Week 3** | | **7.5h** | |

### Week 4: Backfill & Cleanup

| Task | File | Effort | Owner |
|------|------|--------|-------|
| Backfill script and testing | sql/migrations/XXX_backfill_fixture_fields.sql | 1h | DB |
| Deprecation notes in API docs | docs/jlrs_api_contract.md | 0.5h | Docs |
| Migration guide for external API | docs/fixture_semantics_migration.md | 1.5h | Docs |
| Comprehensive integration test | tests/integration/test_fixture_migration_e2e.py | 2h | QA |
| **Subtotal Week 4** | | **5h** | |

**Total Effort**: ~23.5 hours  
**Timeline**: 4 weeks @ 6h/week (part-time) or 1 week @ full-time

---

## IV. Risk Assessment & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Partial migrations create inconsistency | High | Enforce feature flag: all-or-nothing per module |
| Analytics queries break during transition | High | Dual-write (both old & new fields) for 1 release |
| Frontend doesn't gracefully handle missing fields | Medium | Default to legacy match_category if new fields absent |
| Historical data cannot be precisely backfilled | Medium | Accept approximate mapping; note in docs |
| External API consumers break | Medium | 2-release deprecation period; clear changelog |

---

## V. Testing Strategy

### Unit Tests
- match_service: new field extraction and storage
- player_service: role exposure calculation
- analytics: gap_band filtering vs match_category

### Integration Tests
- Event fixture generation → match submission → rating application (full flow)
- Analytics report generation with new fields
- Frontend fixture rendering with all gap_band/role combinations

### Regression Tests
- Existing velocity report still works (backward compat)
- Fixture display doesn't break for legacy match_category-only slots
- Match submission accepts both old and new fixtures

---

## VI. API Contract Changes

### Breaking Changes: None
(All changes are additive; match_category retained for compatibility)

### New Fields on Existing Endpoints

#### GET /events/{event_id}/fixture-slots
Response `EventFixtureSlot` now includes:
- `round_intent`: COMPETITIVE | DEVELOPMENTAL
- `gap_band`: COMPETITIVE | STRETCH | OUT_OF_BAND | BYE
- `player_a_role`: PEER | ANCHORING | STRETCHING | BYE
- `player_b_role`: PEER | ANCHORING | STRETCHING | BYE

(Already present in current types; no schema change required)

#### GET /analytics/players/{player_id}/velocity
Response `VelocityReport` gains optional:
- `gap_band_breakdown`: object with competitive/stretch/out_of_band stats
- `role_breakdown`: object with peer/anchoring/stretching stats

#### New Endpoints
- `GET /events/{event_id}/fixture-quality-report` — fixture semantics summary
- `GET /fixture-slots/{slot_id}` — individual slot detail (if not already exposed)

---

## VII. Configuration Requirements

No new configuration keys required; all migrations use existing logic or derive from new schema fields.

---

## VIII. Success Criteria

- [ ] All services (match, player, leaderboard) consume new fixture fields
- [ ] Analytics endpoints provide gap_band and role breakdowns
- [ ] Frontend displays round_intent, gap_band, and roles in fixture UI
- [ ] 100% of new test cases pass
- [ ] Zero regressions in existing test suite (36/36 unit tests pass)
- [ ] Performance: no degradation in fixture generation or query times
- [ ] Documentation: API contract updated; migration guide published

---

## Appendix: SQL Schema Changes

```sql
-- Migration: Add fixture semantic fields to match table

ALTER TABLE match ADD COLUMN IF NOT EXISTS gap_band gap_band;
ALTER TABLE match ADD COLUMN IF NOT EXISTS round_intent round_intent;
ALTER TABLE match ADD COLUMN IF NOT EXISTS player_a_role player_role;
ALTER TABLE match ADD COLUMN IF NOT EXISTS player_b_role player_role;

-- Create indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_match_gap_band ON match(gap_band);
CREATE INDEX IF NOT EXISTS idx_match_round_intent ON match(round_intent);
```

---

## References

- **Fixture Engine Plan**: docs/fixture_engine_phased_impl_plan.md
- **Critique Items**: docs/fixture_engine_best_of_both_critique.md
- **Rating Math**: app/utils/rating_math.py (for Config pattern)
- **Config Externalization**: docs/downstream_migration_comprehensive_plan.md (this document)

