# Fixture Engine v2: Executive Summary

**Date**: May 29, 2026  
**Status**: Comprehensive migration plan complete  
**Deliverables**: 3 detailed documentation files + implementation roadmap

---

## What Changed in the Fixture Engine

The fixture engine now outputs **richer semantic fields** alongside the legacy `match_category`:

| Field | Type | Purpose |
|-------|------|---------|
| `round_intent` | COMPETITIVE \| DEVELOPMENTAL | Round-level coaching strategy |
| `gap_band` | COMPETITIVE \| STRETCH \| OUT_OF_BAND \| BYE | Per-match fairness classification |
| `player_a_role` | PEER \| ANCHORING \| STRETCHING \| BYE | Player A's position in matchup |
| `player_b_role` | PEER \| ANCHORING \| STRETCHING \| BYE | Player B's position in matchup |
| `match_category` | COMPETITIVE \| STRETCH \| ANCHOR | **Legacy** (derives from gap_band + roles) |

---

## What Needs to Migrate

### 🔴 CRITICAL (Week 1-2)

**match_service.py** — Currently reads only `match_category` from fixture slots
- SELECT fixture slot fields: extend to include `gap_band, round_intent, player_a_role, player_b_role`
- INSERT match record: store all new fields
- Match table schema: add 4 new columns with appropriate types
- Rating eligibility: use `gap_band` instead of inferred `match_category`
- **Impact**: ~3 hours; blocks all downstream work

**Database migrations** (2 files)
- Add columns to match table
- Backfill existing matches from fixture references
- **Impact**: ~1 hour; must run before match_service changes

### 🟡 HIGH PRIORITY (Week 2-3)

**EventDetailPanel.tsx** — Frontend display still infers roles from ratings
- New function: `getMatchMetaFromFixtureSlot()` using explicit fields
- Update fixture rendering to show `gap_band` badges and explicit roles
- Add `round_intent` indicator
- **Impact**: ~2 hours; improves UX significantly

**analytics.py** — Velocity reports filter on `match_category`
- Replace `match_category = 'STRETCH'` with `gap_band = 'STRETCH'`
- Add role breakdown and gap_band breakdown to reports
- **Impact**: ~2 hours; unblocks analytics insights

### 🟢 MEDIUM PRIORITY (Week 3-4)

**player_service.py** — Add role exposure tracking
- New method: `get_player_role_exposure()` for role distribution analysis
- Integrate into player stats endpoint
- **Impact**: ~1.5 hours; enables role-based insights

**event_service.py** — Add fixture quality reporting
- New endpoint: GET /events/{event_id}/fixture-quality-report
- Returns distribution by gap_band, round_intent, roles
- **Impact**: ~2 hours; event organizers assess fixture balance

**MatchDetail.tsx** — Complement match display with fixture context
- Show gap_band, round_intent, and roles in match detail
- **Impact**: ~1.5 hours; polish

---

## Three Comprehensive Documents Created

### 📋 1. **downstream_migration_comprehensive_plan.md**
**Full roadmap with timelines**
- 4-phase implementation plan (Week 1-4)
- Detailed changes per component with code context
- Risk assessment and testing strategy
- API contract changes
- Success criteria

**Use this to**: Plan resource allocation, set timelines, coordinate teams

### 📋 2. **fixture_engine_v2_enumeration.md**
**Quick reference: all components and issues**
- 11 components requiring updates (with priority levels)
- Dependency graph showing what blocks what
- Field semantics reference (meaning of each new field)
- Testing checklist (19 items)
- File change summary (backend, frontend, docs)

**Use this to**: Understand full scope, identify dependencies, communicate impact

### 📋 3. **fixture_v2_code_change_spec.md**
**Detailed code-level specifications**
- SQL migrations (with exact DDL statements)
- Before/after code for each service
- Exact line numbers and context
- New functions with full implementation
- Type definitions
- Test specifications

**Use this to**: Implement changes, review PRs, ensure consistency

---

## Key Statistics

| Metric | Value |
|--------|-------|
| **Effort (total)** | 20-23 hours |
| **Recommended pace** | 1 week full-time OR 4 weeks part-time |
| **Files to modify** | 11 (8 backend, 3 frontend) |
| **New SQL migrations** | 2 |
| **Database columns added** | 4 (match table) |
| **New endpoints** | 1 (fixture quality report) |
| **New service methods** | 4 (role exposure, gap_band checks, etc.) |
| **Breaking changes** | 0 (all backward compatible) |
| **Deprecation period** | 2 releases (match_category) |

---

## Implementation Flow

```
WEEK 1: Core Services
├─ Add match table columns (SQL migrations)
├─ Update match_service.py (SELECT, INSERT, eligibility)
├─ Create unit tests (match_service)
└─ BLOCKERS CLEARED ✅

WEEK 2: Analytics & Reports
├─ Update analytics.py (gap_band filtering + breakdowns)
├─ Add player_service role exposure tracking
├─ Add event_service fixture quality endpoint
├─ Create integration tests (analytics + quality)
└─ Core backend complete ✅

WEEK 3: Frontend Display
├─ EventDetailPanel.tsx (new function + rendering)
├─ MatchDetail.tsx (add fixture context)
├─ Type schema verification
└─ Frontend UX complete ✅

WEEK 4: Validation & Cleanup
├─ Backfill historical data (if needed)
├─ Comprehensive e2e tests (full flow)
├─ Deprecation documentation
└─ Migration complete ✅
```

---

## Field Mapping Reference

### How roles are inferred from gap_band

```
gap_band          player_role (if assigned that role)    meaning
────────────────────────────────────────────────────────────────
COMPETITIVE  +    PEER                          → similar skill
STRETCH      +    ANCHORING                     → playing down
STRETCH      +    STRETCHING                    → playing up
OUT_OF_BAND  +    ANCHORING|STRETCHING          → exception (gap > 250)
BYE          +    BYE                           → no opponent

NOTE: gap_band derives from actual rating gap calculation.
      player_*_role is assigned based on gap_band and opponent position.
```

### match_category (legacy) → new semantics

```
match_category   ≈ gap_band + roles
────────────────────────────────────────────────
COMPETITIVE      = COMPETITIVE + PEER (both)
STRETCH          = STRETCH + (STRETCHING | ANCHORING | PEER)
ANCHOR           = STRETCH + ANCHORING (legacy, not used by engine)

⚠️ Legacy field is lossy: doesn't capture player-specific role,
   can't distinguish STRETCHING from ANCHORING.
```

---

## Testing Strategy

### Unit Tests (match_service)
- ✅ New fields extracted from fixture slots
- ✅ Gap band eligibility logic (COMPETITIVE, STRETCH, OUT_OF_BAND, BYE)
- ✅ Legacy fallback (matches without fixtures)

### Integration Tests (full flow)
- ✅ Event fixture generation → match submission → rating application
- ✅ Analytics reports (gap_band filtering, role breakdowns)
- ✅ Fixture quality report accuracy
- ✅ Backward compatibility (legacy match_category queries still work)

### Regression Tests
- ✅ All 36 existing unit tests pass (0 failures expected)
- ✅ Existing leaderboard/analytics endpoints work unchanged
- ✅ Legacy API consumers unaffected

---

## API Changes Summary

### No Breaking Changes
All changes are **additive**; existing clients continue to work.

### New Fields on Existing Endpoints

**GET /events/{event_id}/fixture-slots** (EventFixtureSlot)
```typescript
// Already in response (no schema change needed):
round_intent: "COMPETITIVE" | "DEVELOPMENTAL"
gap_band: "COMPETITIVE" | "STRETCH" | "OUT_OF_BAND" | "BYE"
player_a_role: "PEER" | "ANCHORING" | "STRETCHING" | "BYE"
player_b_role: "PEER" | "ANCHORING" | "STRETCHING" | "BYE"
```

**GET /analytics/players/{player_id}/velocity** (VelocityReport)
```typescript
// Added optional fields:
role_breakdown?: {
  peer: { wins: number, total: number }
  anchoring: { wins: number, total: number }
  stretching: { wins: number, total: number }
}
gap_band_breakdown?: {
  competitive: { wins: number, total: number }
  stretch: { wins: number, total: number }
  out_of_band: { wins: number, total: number }
}
```

### New Endpoints

**GET /events/{event_id}/fixture-quality-report**
```json
{
  "event_id": "...",
  "total_slots": 48,
  "by_gap_band": {
    "COMPETITIVE": 24,
    "STRETCH": 16,
    "OUT_OF_BAND": 2,
    "BYE": 6
  },
  "by_round_intent": {
    "COMPETITIVE": 40,
    "DEVELOPMENTAL": 8
  },
  "role_distribution": {
    "PEER": 32,
    "ANCHORING": 6,
    "STRETCHING": 4
  },
  "cross_academy_pct": 85.7
}
```

---

## Deprecation Plan

| Timeline | Action |
|----------|--------|
| **v2.5** (current) | `match_category` kept, new fields added |
| **v2.6** | Deprecation warning added to API docs |
| **v2.7** (est. 2026-Q3) | `match_category` removed from all endpoints |

External API consumers: **2-release window to migrate** (clear changelog provided)

---

## Deployment Checklist

- [ ] Review all 3 documentation files
- [ ] Estimate team capacity and timeline
- [ ] Assign tasks to backend/frontend/QA
- [ ] Create feature branch
- [ ] Implement SQL migrations (test on staging)
- [ ] Implement backend changes (1 file at a time)
- [ ] Implement frontend changes
- [ ] Run full test suite (including new tests)
- [ ] Staging: full e2e testing
- [ ] Code review + approval
- [ ] Production deployment
- [ ] Monitor for errors (logging on new fields)
- [ ] Publish migration guide for external API users

---

## File References

All documentation has been created in the workspace:

1. **docs/downstream_migration_comprehensive_plan.md** — Full roadmap
2. **docs/fixture_engine_v2_enumeration.md** — Quick reference
3. **docs/fixture_v2_code_change_spec.md** — Code-level specs

These are ready for team review and can be shared with stakeholders.

---

## Next Steps

1. **Review** all three documents
2. **Assign** Phase 1 (match_service) to senior backend engineer
3. **Plan** Phase 2 (analytics) in parallel
4. **Coordinate** Phase 3 (frontend) with frontend team
5. **Schedule** testing and deployment

Estimated total effort: **4 weeks @ 5-6h/week** or **1 week @ full-time**

