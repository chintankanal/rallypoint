# Fixture Engine v2 Downstream Services Enumeration

## Quick Reference: All Components Requiring Updates

### 🔴 HIGH PRIORITY (Core Functionality)

#### Backend Services
1. **app/services/match_service.py** (Lines 195-211, 237-267)
   - ❌ **Issue**: Reads only `match_category` from fixture slots
   - ✅ **Fix**: Extend SELECT to include `gap_band`, `round_intent`, `player_a_role`, `player_b_role`
   - ✅ **Fix**: Store these fields in match table (new columns)
   - ✅ **Fix**: Use `gap_band` for rating eligibility checks instead of legacy `match_category`
   - **Impact**: All match submissions lose rich fixture semantics

2. **Database Schema: match table**
   - ❌ **Issue**: Missing `gap_band`, `round_intent`, `player_a_role`, `player_b_role`
   - ✅ **Fix**: Add 4 new columns with appropriate types
   - ✅ **Fix**: Backfill existing matches from fixture_slot/event_fixture_slot reference
   - **Impact**: Cannot query matches by role or gap_band

#### Frontend Display
3. **web/src/components/EventDetailPanel.tsx** (Lines 46-62, 355+)
   - ❌ **Issue**: `getMatchTypeMeta()` infers roles from ratings instead of using explicit fields
   - ❌ **Issue**: Fixture matrix renders only legacy match_category
   - ✅ **Fix**: Create `getMatchMetaFromFixtureSlot()` using explicit (gap_band, role) tuple
   - ✅ **Fix**: Update fixture rendering to show `round_intent`, `gap_band`, and roles
   - ✅ **Fix**: Render visual indicators for player role (PEER/ANCHORING/STRETCHING)
   - **Impact**: Coaches & players don't see true fixture semantics; inference errors possible

---

### 🟡 MEDIUM PRIORITY (Analytics & Insights)

#### Analytics & Reporting
4. **app/routers/analytics.py** (Lines 49-50, 60-80)
   - ❌ **Issue**: Velocity report filters on `match_category = 'STRETCH'` instead of `gap_band`
   - ❌ **Issue**: No role-based match breakdown
   - ✅ **Fix**: Replace `match_category` filter with `gap_band = 'STRETCH'`
   - ✅ **Fix**: Add optional fields to VelocityReport: `gap_band_breakdown`, `role_breakdown`
   - **Impact**: Analytics reports show inaccurate STRETCH metrics; no role insights

5. **app/services/event_service.py** (New functionality)
   - ❌ **Issue**: No fixture quality/semantics reporting endpoint
   - ✅ **Fix**: Add `get_fixture_quality_report(event_id)` endpoint
   - ✅ **Fix**: Return distribution by gap_band, round_intent, roles, balance metrics
   - **Impact**: Event organizers cannot assess fixture quality

6. **app/services/leaderboard_service.py**
   - ❌ **Issue**: Only aggregates by match_category (if at all)
   - ✅ **Fix**: Add `get_match_breakdown_by_gap_band()` method
   - ✅ **Fix**: Track wins/losses per gap_band and per role
   - **Impact**: Leaderboard missing fairness context (competitive vs stretch performance)

7. **app/services/player_service.py**
   - ❌ **Issue**: No role-based exposure tracking
   - ✅ **Fix**: Add `get_player_role_exposure(player_id, period_days)` method
   - ✅ **Fix**: Return { peer_matches, anchoring_matches, stretching_matches, bye_count }
   - **Impact**: Cannot assess player's role diversity or balance

---

### 🟢 LOWER PRIORITY (Polish & Historical)

#### Frontend Components
8. **web/src/components/MatchDetail.tsx**
   - ❌ **Issue**: Displays match result but not source fixture semantics
   - ✅ **Fix**: Fetch and display gap_band, round_intent, and roles
   - ✅ **Fix**: Add new endpoint `GET /fixture-slots/{slot_id}` if needed
   - **Impact**: Match detail view lacks context

#### Frontend Types
9. **web/src/types/match.ts**
   - ✅ **Status**: Already includes new fields in EventFixtureSlot (via API client)
   - ℹ️ **Action**: No changes needed (types already correct)

#### Historical Data
10. **Database: fixture_slot backfill** (INTRA_ACADEMY sessions)
    - ❌ **Issue**: Existing sessions may lack new fields
    - ✅ **Fix**: Backfill using migration script
    - ✅ **Fix**: Map legacy `match_category` to `gap_band` approximately
    - ⚠️ **Note**: Cannot precisely recover historical roles (not stored in legacy fields)

11. **API Deprecation Plan**
    - ❌ **Issue**: No deprecation timeline for `match_category`
    - ✅ **Fix**: Add deprecation notice in API docs
    - ✅ **Fix**: Set 2-release deprecation window
    - ✅ **Fix**: Create migration guide for external consumers
    - **Impact**: External integrations may break without warning

---

## Dependency Graph

```
fixture_engine (outputs new fields)
    ↓
match_service.py (MUST update first)
    ↓
    ├─→ match table schema (MUST add columns)
    │
    ├─→ analytics.py (depends on match.gap_band)
    │   ├─→ velocity reports
    │   └─→ EventDetailPanel.tsx (display)
    │
    ├─→ player_service.py (optional: role exposure)
    │   └─→ player stats endpoints
    │
    ├─→ leaderboard_service.py (optional: gap_band breakdown)
    │   └─→ leaderboard pages
    │
    └─→ event_service.py (new: fixture quality)
        └─→ EventDetailPanel.tsx (warnings/metrics)

EventDetailPanel.tsx (MUST update display)
    ├─→ getMatchMetaFromFixtureSlot() (new function)
    ├─→ round_intent rendering
    ├─→ gap_band badge rendering
    ├─→ role indicators (PEER/ANCHORING/STRETCHING)
    └─→ MatchDetail.tsx (complement)

match_category field (legacy)
    └─→ Deprecate ONLY after all above complete
```

---

## Field Semantics Reference

### Round Intent
- **COMPETITIVE**: Players should be close skill level; aim for tight pairings
- **DEVELOPMENTAL**: Intentional skill spread; learning-focused round

### Gap Band
- **COMPETITIVE**: Rating gap ≤ 100 → head-to-head with similar skill
- **STRETCH**: Rating gap 100 < gap ≤ 250 → developmental or anchor scenario
- **OUT_OF_BAND**: Rating gap > 250 but ≤ 500 (exception; shouldn't be rated eligible)
- **BYE**: Player has no opponent; sits out this round

### Player Role
- **PEER**: Similar skill level to opponent (gap ≤ 100)
- **STRETCHING**: Playing against stronger opponent (gap > 0, role is stretching)
- **ANCHORING**: Playing against weaker opponent (gap > 0, role is anchoring)
- **BYE**: No opponent

### Legacy match_category (being phased out)
- **COMPETITIVE**: Equivalent to gap_band COMPETITIVE + role PEER
- **STRETCH**: Equivalent to gap_band STRETCH (could be ANCHORING or STRETCHING)
- **ANCHOR**: Specific to player_b_role ANCHORING (not used by engine; inferred from roles)

---

## Testing Checklist

- [ ] match_service correctly reads and stores all new fields
- [ ] match table columns exist and are properly typed
- [ ] analytics queries on gap_band return same results as legacy match_category
- [ ] velocity report includes role_breakdown and gap_band_breakdown (optional fields)
- [ ] event_service fixture quality endpoint returns valid report
- [ ] player_service role exposure tracking works for all 90-day windows
- [ ] EventDetailPanel renders all four role indicators correctly
- [ ] EventDetailPanel displays round_intent and gap_band badges
- [ ] MatchDetail shows fixture context (if endpoint exists)
- [ ] Existing unit tests pass (36/36)
- [ ] New migration tests pass (backfill accuracy, no data loss)
- [ ] Backward compat: legacy match_category queries still work

---

## Estimated Effort

| Phase | Component | Effort | Risk |
|-------|-----------|--------|------|
| 1 | match_service + schema | 3h | HIGH (core) |
| 1 | Unit tests (match) | 2h | MED |
| 2 | Analytics migration | 3h | MED |
| 2 | player_service roles | 2h | LOW |
| 2 | leaderboard roles | 2h | LOW |
| 3 | EventDetailPanel | 3h | HIGH (UX) |
| 3 | MatchDetail | 2h | LOW |
| 4 | Backfill + tests | 2h | MED |
| 4 | Deprecation docs | 1h | LOW |
| **Total** | | **20-23h** | |

**Recommended pace**: 1 week full-time or 4 weeks part-time (5-6h/week)

---

## Files Changed Summary

### Backend (8 files)
- sql/migrations/XXX_match_fixture_fields.sql (NEW)
- sql/migrations/XXX_backfill_fixture_fields.sql (NEW)
- app/services/match_service.py (MODIFY)
- app/services/player_service.py (ADD methods)
- app/services/leaderboard_service.py (ADD methods)
- app/services/event_service.py (ADD endpoint)
- app/routers/analytics.py (MODIFY)
- tests/integration/test_fixture_migration_e2e.py (NEW)

### Frontend (3 files)
- web/src/components/EventDetailPanel.tsx (MODIFY)
- web/src/components/MatchDetail.tsx (MODIFY)
- web/src/types/match.ts (NO CHANGE - already correct)

### Documentation (2 files)
- docs/fixture_engine_phased_impl_plan.md (UPDATE status)
- docs/jlrs_api_contract.md (ADD deprecation note)
- docs/fixture_semantics_migration.md (NEW)

---

## Success Metrics

✅ **Functional**: All new fields read/written/displayed  
✅ **Performance**: No query regression vs legacy approach  
✅ **Compat**: Legacy match_category still works; 2-release deprecation  
✅ **Coverage**: 100% of new test cases pass; 0 regression failures  
✅ **UX**: Fixture display now shows authoritative role/gap semantics (not inferred)

