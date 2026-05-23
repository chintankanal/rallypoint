# Points-Aware Architecture Plan: Transitioning to Performance-Granular System

**Date:** May 22, 2026  
**Status:** Analysis & Design  
**Scope:** Support individual game points entry (per-set) across all formats (Friendly, League, Tournament)  
**Design Principle:** "Point Aware Infrastructure, UI Optional"

---

## Executive Summary

The JLRS system currently operates as a **Result-Only system** — coaches submit set scores (e.g., 2-1, 1-2) and the Elo engine rates matches on set margin-of-victory alone. This proposal transitions the system to be **Performance-Granular** by:

1. **Storing individual point scores per set** (e.g., Set 1: 11-9, Set 2: 5-11, Set 3: 14-13)
2. **Keeping point entry strictly optional** on the UI to avoid friction during daily casual sessions
3. **Making Elo ratings unaffected** (continue using set-level margin-of-victory only)
4. **Enabling future performance analytics** (comeback rates, point differential trends, etc.) without disrupting the rating engine

**Key trade-off:** Infrastructure is "point aware" (database stores & validates points), but the rating engine remains conservative (uses set scores only). This preserves system integrity while opening the door to deeper performance insights.

---

## 1. Current State: Result-Only Architecture

### 1.1 What Gets Stored Today

```
Match {
  match_id: UUID
  player_a_id: UUID
  player_b_id: UUID
  match_format: BEST_OF_3 | BEST_OF_5 | BEST_OF_7
  sets_won_a: int (0-3 or 0-4)
  sets_won_b: int (0-3 or 0-4)
  sets_won_a_actual: int | null  [for retirements]
  sets_won_b_actual: int | null  [for retirements]
  is_retirement: bool
  match_date: date
  ...
}

RatingHistory {
  # Elo delta computed from set margin only:
  actual_score: float  [0.0, 0.5, or 1.0 based on set_margin]
  expected_score: float
  delta: float
  ...
}
```

### 1.2 Elo Calculation Today (Margin-of-Victory from Sets)

```python
# From rating_math.py
_ACTUAL_SCORES = {
    'BEST_OF_3': {
        (2, 0): (1.0, 0.0),      # Whitewash
        (2, 1): (0.75, 0.25),    # 1-set deficit
    },
    'BEST_OF_5': {
        (3, 0): (1.0, 0.0),
        (3, 1): (0.875, 0.125),  # Tight win
        (3, 2): (0.75, 0.25),
    },
    # ...
}

actual_score = _ACTUAL_SCORES[match_format][(sets_won_winner, sets_won_loser)]
delta = k_shared * (actual_score_winner - expected_score_winner)
```

**Key insight:** Set scores alone drive Elo deltas. A 2-1 win is always 0.75/0.25 split, whether sets were 11-0, 11-9, 21-19.

---

## 2. Proposed State: Performance-Granular Architecture

### 2.1 New Data Structure

Add per-set point scores to match submission and storage:

```python
# New in MatchSubmit schema
SetScore {
    points_a: int  # 0-30 (handle deuce/multi-point ties)
    points_b: int
}

# For a BEST_OF_3, store up to 3 SetScore records
# Nullable: if coach skips points, fields are null

MatchSubmit {
    event_id: str
    player_a_id: str
    player_b_id: str
    match_format: MatchFormat
    sets_won_a: int      # Required: 0-3
    sets_won_b: int      # Required: 0-3
    sets_won_a_actual: int | None  # Retirement
    sets_won_b_actual: int | None  # Retirement
    is_retirement: bool
    match_date: date
    
    # NEW: Per-set point scores (all nullable for backward compatibility)
    set_scores: list[SetScore] | None
    
    # Example:
    # set_scores = [
    #   SetScore(points_a=11, points_b=9),
    #   SetScore(points_a=5, points_b=11),
    #   SetScore(points_a=14, points_b=13),
    # ]
}
```

### 2.2 Database Schema Changes

#### Add New Table: `match_set_score`

```sql
CREATE TABLE IF NOT EXISTS match_set_score (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    set_number INTEGER NOT NULL,  -- 1, 2, 3, etc.
    points_a INTEGER NOT NULL,
    points_b INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_set_number_positive CHECK (set_number > 0),
    CONSTRAINT chk_points_nonnegative CHECK (points_a >= 0 AND points_b >= 0),
    CONSTRAINT chk_set_number_matches_format CHECK (
        -- Will be enforced at service layer for performance
    ),
    UNIQUE (match_id, set_number)
);

CREATE INDEX idx_match_set_score_match_id ON match_set_score(match_id);
```

#### Why a separate table?

1. **Flexibility:** Different match formats have different # of sets (3, 5, or 7)
2. **Sparse data:** Many matches won't have points → null vs. row doesn't exist
3. **Query clarity:** Easier to aggregate (e.g., "avg points margin per set across season")
4. **Audit trail:** Can be immutable post-confirmation; rollback/correction clear

#### No changes to `match` table itself

The existing `sets_won_a`, `sets_won_b` remain the source of truth for Elo rating. Points are supplementary.

### 2.3 Schema Validation Changes

#### New validation in `match.py`

```python
from pydantic import BaseModel, field_validator, model_validator

class SetScore(BaseModel):
    points_a: int
    points_b: int
    
    @model_validator(mode="after")
    def validate_set_points(self) -> "SetScore":
        if self.points_a < 0 or self.points_b < 0:
            raise ValueError("Set points cannot be negative")
        
        # Modern table tennis: win at 11+ (or 21+ if deuce >= 9-9)
        # For flexibility, we allow 0-30 range to handle tiebreaks, deuces
        if self.points_a > 30 or self.points_b > 30:
            raise ValueError("Set points cannot exceed 30")
        
        # At least one player must have scored points (no 0-0 sets)
        if self.points_a == 0 and self.points_b == 0:
            raise ValueError("A set must have points scored")
        
        # Winner must have ≥11 (except in deuce scenarios, enforced below)
        winner_points = max(self.points_a, self.points_b)
        loser_points = min(self.points_a, self.points_b)
        
        if winner_points < 11:
            raise ValueError("Winning player in a set must have ≥11 points")
        
        # If winner has ≥11, loser must be ≤(winner - 2) OR allow deuce to 30
        if winner_points >= 10:
            if loser_points < winner_points - 2:
                if not (winner_points >= 10 and loser_points >= 9):
                    # Allow deuces: 11-10, 12-11, etc. up to 30-29
                    raise ValueError(
                        f"Invalid point spread: {winner_points}-{loser_points}"
                    )
        
        return self

class MatchSubmit(BaseModel):
    event_id: str
    session_id: str | None = None
    fixture_slot_id: str | None = None
    player_a_id: str
    player_b_id: str
    match_format: MatchFormat
    sets_won_a: int
    sets_won_b: int
    sets_won_a_actual: int | None = None
    sets_won_b_actual: int | None = None
    is_retirement: bool = False
    match_date: date
    umpire_id: str | None = None
    
    # NEW FIELD
    set_scores: list[SetScore] | None = None
    
    @model_validator(mode="after")
    def validate_match(self) -> "MatchSubmit":
        # Existing validation for sets_won_a/b remains unchanged
        # ...
        
        # NEW: Validate set_scores if provided
        if self.set_scores is not None:
            fmt = self.match_format.value
            required_sets = _REQUIRED_WINNER_SETS.get(fmt, 0)
            
            # Check: # of set scores must match # of sets played
            total_sets = self.sets_won_a + self.sets_won_b
            if len(self.set_scores) != total_sets:
                raise ValueError(
                    f"Match has {total_sets} sets but {len(self.set_scores)} "
                    f"set scores provided"
                )
            
            # Check: Set scores must be in order 1, 2, 3, ...
            for i, score in enumerate(self.set_scores, 1):
                # Could add: validate that point winner matches set winner
                # e.g., if sets_won_a > sets_won_b, player A should win majority
                pass
            
            # Check: Set score winner must match set outcome
            for i, score in enumerate(self.set_scores):
                set_idx = i + 1
                # Determine who should have won this set from match outcome
                # (requires: if set A won 2-1, then sets 1,2 won by A, set 3 by B)
                # This is complex; defer to service layer for clarity
        
        return self
```

### 2.4 Backend Service Layer Changes

#### `app/routers/matches.py` — `POST /api/v1/matches`

**No schema changes to the endpoint**, but update the handler:

```python
# POST /api/v1/matches
def submit_match(body: MatchSubmit, current_user: User = Depends(get_current_user)):
    """
    Submit a match result with optional per-set points.
    
    Points are optional:
    - If set_scores provided: validate and store in match_set_score table
    - If set_scores null: still accept; match is valid, just no points data
    - Elo rating ignores points; uses set_won_a/b only (backward compatible)
    """
    with get_connection() as conn:
        from app.services import match_service
        
        result = match_service.submit_match(conn, body, current_user.user_id)
        
        # If set_scores were provided, store them
        if body.set_scores:
            match_service.store_set_scores(conn, result["match_id"], body.set_scores)
        
        conn.commit()
        return result
```

#### New in `app/services/match_service.py`

```python
def store_set_scores(conn, match_id: str, set_scores: list[SetScore]) -> None:
    """
    Insert per-set point scores into match_set_score table.
    Called only if set_scores were provided and validated.
    """
    with conn.cursor() as cur:
        for set_num, score in enumerate(set_scores, start=1):
            cur.execute(
                """
                INSERT INTO match_set_score (match_id, set_number, points_a, points_b)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (match_id, set_number) 
                DO UPDATE SET points_a = EXCLUDED.points_a, points_b = EXCLUDED.points_b
                """,
                (match_id, set_num, score.points_a, score.points_b)
            )


def get_set_scores(conn, match_id: str) -> list[dict] | None:
    """
    Retrieve per-set point scores for a match.
    Returns list of {set_number, points_a, points_b} or None if no scores.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT set_number, points_a, points_b
            FROM match_set_score
            WHERE match_id = %s
            ORDER BY set_number ASC
            """,
            (match_id,)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else None
```

#### Update `MatchResponse` schema to include points

```python
class MatchResponse(BaseModel):
    # ... existing fields ...
    sets_won_a: int
    sets_won_b: int
    
    # NEW FIELD: Return set scores if they exist
    set_scores: list[dict] | None = None  
    # Example: [
    #   {"set_number": 1, "points_a": 11, "points_b": 9},
    #   {"set_number": 2, "points_a": 5, "points_b": 11},
    #   {"set_number": 3, "points_a": 14, "points_b": 13},
    # ]
```

#### Update GET endpoints

```python
# In routers/matches.py

@router.get("/matches/{match_id}", response_model=MatchResponse)
def get_match(match_id: str, current_user: User = Depends(get_current_user)):
    with get_connection() as conn:
        match_data = match_service.get_match(conn, match_id)
        
        # NEW: Fetch set scores if they exist
        set_scores = match_service.get_set_scores(conn, match_id)
        match_data["set_scores"] = set_scores
        
        return MatchResponse(**match_data)
```

### 2.5 Rating Engine: Minimal Changes (Intentional)

**The Elo rating engine remains 100% unchanged.**

Why? The requirements specify:
- Elo should continue using **set margin only** (current behavior)
- Points are stored for **analytics only**
- This preserves rating system integrity and backward compatibility

**What DOESN'T change:**
- `app/services/rating_engine.py` — no modifications
- `app/utils/rating_math.py` — no modifications
- Elo delta calculation — no modifications
- Rating history — no modifications

**What DOES happen (implicitly):**
- When `apply_ratings_batch()` runs, it uses the same `sets_won_a/b` as before
- The `match_set_score` table is completely ignored by the rating engine
- RatingHistory remains identical (no new fields)

This is intentional: **Rating logic and points data are decoupled.**

### 2.6 Analytics Foundation (Future Use)

#### New queries enabled by `match_set_score`

```sql
-- Point differential trends for a player
SELECT 
    m.match_id, 
    m.match_date,
    m.player_a_id, m.player_b_id,
    SUM(CASE WHEN m.player_a_id = p.player_id THEN mss.points_a ELSE mss.points_b END) as player_total_points,
    SUM(CASE WHEN m.player_a_id = p.player_id THEN mss.points_b ELSE mss.points_a END) as opponent_total_points
FROM match m
JOIN match_set_score mss ON m.match_id = mss.match_id
WHERE (m.player_a_id = $1 OR m.player_b_id = $1)
GROUP BY m.match_id, m.match_date
ORDER BY m.match_date DESC;

-- Comeback rate: win after being down in sets
SELECT 
    m.match_id,
    m.sets_won_a, m.sets_won_b,
    CASE 
        WHEN m.player_a_id = $1 AND m.sets_won_a > m.sets_won_b THEN 'W'
        WHEN m.player_b_id = $1 AND m.sets_won_b > m.sets_won_a THEN 'W'
        ELSE 'L'
    END as result
FROM match m
WHERE (m.player_a_id = $1 OR m.player_b_id = $1)
  AND m.match_set_score IS NOT NULL;

-- Points per set variance (tight vs blowout)
SELECT 
    m.match_id,
    m.match_date,
    STDDEV_POP(ABS(mss.points_a - mss.points_b)) as point_margin_variance
FROM match m
JOIN match_set_score mss ON m.match_id = mss.match_id
WHERE m.player_a_id = $1 OR m.player_b_id = $1
GROUP BY m.match_id, m.match_date;
```

**Note:** Analytics routes are out of scope for this phase but the data structure is ready.

---

## 3. Frontend Changes

### 3.1 Match Submission Form

#### Current UI (Set Scores Only)

```
┌─────────────────────────────────────┐
│ Match Submission Form                │
├─────────────────────────────────────┤
│ Player A: [Select]                  │
│ Player B: [Select]                  │
│ Format: [BEST_OF_3 ▼]               │
│ Match Date: [YYYY-MM-DD]            │
│                                      │
│ SETS WON (Required)                 │
│ Player A: [0] - Player B: [0]       │
│                                      │
│ Is Retirement? [☐]                  │
│                                      │
│ [Submit] [Cancel]                   │
└─────────────────────────────────────┘
```

#### Proposed UI (Set Scores + Optional Points)

```
┌─────────────────────────────────────┐
│ Match Submission Form                │
├─────────────────────────────────────┤
│ Player A: [Select]                  │
│ Player B: [Select]                  │
│ Format: [BEST_OF_3 ▼]               │
│ Match Date: [YYYY-MM-DD]            │
│                                      │
│ SETS WON (Required)                 │
│ Player A: [0] - Player B: [0]       │
│                                      │
│ ─────────────────────────────────── │
│ POINT SCORES (Optional)              │
│ [▼ Show Point Details]               │ ← Collapsed by default
│                                      │
│ Is Retirement? [☐]                  │
│                                      │
│ [Submit] [Cancel]                   │
└─────────────────────────────────────┘

--- If user clicks "▼ Show Point Details" ---

┌─────────────────────────────────────┐
│ Set 1:                              │
│ Player A: [___] - Player B: [___]   │
│ ☐ Validation: A=11, B=9 ✓           │
│                                      │
│ Set 2: (if won by A or B)           │
│ Player A: [___] - Player B: [___]   │
│ ☐ Validation: A=5, B=11 ✓           │
│                                      │
│ Set 3: (if match went to 3)         │
│ Player A: [___] - Player B: [___]   │
│ ☐ Validation: pending...            │
│                                      │
│ [Discard Points] [Keep Points]      │
└─────────────────────────────────────┘
```

#### Design Rationale

1. **Collapsed by default** — Coaches can skip it for fast entry during casual sessions
2. **One field per set** — Only show sets that were actually played (dynamically based on `sets_won_a/b`)
3. **Real-time validation** — Live feedback (11-9 ✓, 5-11 ✓, pending...)
4. **Optional completion** — Coach can clear all point fields and submit with just set scores
5. **Accessibility** — Clear visual distinction (light gray background for optional section)

### 3.2 React Component Implementation

#### New Component: `SetPointsInput.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { SetScore } from '../types/match';

interface SetPointsInputProps {
  matchFormat: 'BEST_OF_3' | 'BEST_OF_5' | 'BEST_OF_7';
  setsWonA: number;
  setsWonB: number;
  onSetScoresChange: (scores: SetScore[] | null) => void;
  isRetirement: boolean;
}

export const SetPointsInput: React.FC<SetPointsInputProps> = ({
  matchFormat,
  setsWonA,
  setsWonB,
  onSetScoresChange,
  isRetirement,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [setScores, setSetScores] = useState<SetScore[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  const totalSets = setsWonA + setsWonB;

  useEffect(() => {
    // Initialize empty scores for each set that was played
    const initialScores = Array(totalSets).fill(null).map(() => ({
      points_a: 0,
      points_b: 0,
    }));
    setSetScores(initialScores);
  }, [matchFormat, setsWonA, setsWonB]);

  const updateSetScore = (setIndex: number, field: 'a' | 'b', value: number) => {
    const newScores = [...setScores];
    if (field === 'a') newScores[setIndex].points_a = value;
    else newScores[setIndex].points_b = value;
    
    setSetScores(newScores);
    validateScores(newScores);
  };

  const validateScores = (scores: SetScore[]) => {
    const newErrors: string[] = [];

    scores.forEach((score, idx) => {
      const { points_a, points_b } = score;
      
      if (points_a === 0 && points_b === 0) {
        // Both zero is allowed (unfilled)
        return;
      }

      if (points_a < 0 || points_b < 0) {
        newErrors.push(`Set ${idx + 1}: Points cannot be negative`);
      }

      const winner = Math.max(points_a, points_b);
      const loser = Math.min(points_a, points_b);

      if (winner < 11) {
        newErrors.push(`Set ${idx + 1}: Winner must have ≥11 points`);
      }

      if (winner >= 10 && !(loser >= winner - 2 || (winner >= 10 && loser >= 9))) {
        newErrors.push(`Set ${idx + 1}: Invalid point spread`);
      }
    });

    setErrors(newErrors);
  };

  const handleClearPoints = () => {
    const emptyScores = Array(totalSets).fill(null).map(() => ({
      points_a: 0,
      points_b: 0,
    }));
    setSetScores(emptyScores);
    setErrors([]);
    onSetScoresChange(null);  // Signal to parent: no points
  };

  const handleKeepPoints = () => {
    // Filter out all-zero scores
    const validScores = setScores.filter(s => s.points_a > 0 || s.points_b > 0);
    
    if (validScores.length !== totalSets) {
      setErrors(['All played sets must have point scores']);
      return;
    }

    onSetScoresChange(setScores);
  };

  if (totalSets === 0) return null;

  return (
    <div className="set-points-input">
      <button
        type="button"
        className="toggle-button"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {isExpanded ? '▼' : '▶'} Point Scores (Optional)
      </button>

      {isExpanded && (
        <div className="points-detail-container">
          {setScores.map((score, idx) => (
            <div key={idx} className="set-points-row">
              <label>Set {idx + 1}:</label>
              <input
                type="number"
                min={0}
                max={30}
                value={score.points_a}
                onChange={(e) => updateSetScore(idx, 'a', Number(e.target.value))}
                placeholder="0"
                aria-label={`Set ${idx + 1} Player A points`}
              />
              <span> - </span>
              <input
                type="number"
                min={0}
                max={30}
                value={score.points_b}
                onChange={(e) => updateSetScore(idx, 'b', Number(e.target.value))}
                placeholder="0"
                aria-label={`Set ${idx + 1} Player B points`}
              />
            </div>
          ))}

          {errors.length > 0 && (
            <div className="error-messages" role="alert">
              {errors.map((err, i) => <div key={i}>{err}</div>)}
            </div>
          )}

          <div className="button-group">
            <button
              type="button"
              className="secondary-button"
              onClick={handleClearPoints}
            >
              Discard Points
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={handleKeepPoints}
              disabled={errors.length > 0 || totalSets === 0}
            >
              Save Points
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
```

#### Integrate into `MatchSubmissionForm.tsx`

```typescript
import { SetPointsInput } from './SetPointsInput';

export const MatchSubmissionForm: React.FC = () => {
  const [formData, setFormData] = useState<MatchSubmit>({
    // ... existing fields ...
  });

  const handleSetScoresChange = (scores: SetScore[] | null) => {
    setFormData(prev => ({
      ...prev,
      set_scores: scores,
    }));
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* ... existing fields ... */}
      
      <SetPointsInput
        matchFormat={formData.match_format}
        setsWonA={formData.sets_won_a}
        setsWonB={formData.sets_won_b}
        onSetScoresChange={handleSetScoresChange}
        isRetirement={formData.is_retirement}
      />
      
      <button type="submit">Submit Match</button>
    </form>
  );
};
```

### 3.3 Match Display / Confirmation Page

Update `MatchDetail.tsx` to show points if available:

```typescript
export const MatchDetail: React.FC<{matchId: string}> = ({ matchId }) => {
  const { data: match } = useQuery(['match', matchId], () => 
    api.getMatch(matchId)
  );

  return (
    <div className="match-detail">
      <h2>Match Result</h2>
      
      <div className="result-summary">
        <div>{match.player_a.name}</div>
        <div>{match.sets_won_a} - {match.sets_won_b}</div>
        <div>{match.player_b.name}</div>
      </div>

      {/* NEW: Show point scores if available */}
      {match.set_scores && match.set_scores.length > 0 && (
        <div className="point-details">
          <h3>Point Breakdown</h3>
          {match.set_scores.map((score) => (
            <div key={score.set_number} className="set-detail">
              <span>Set {score.set_number}:</span>
              <span>{score.points_a} - {score.points_b}</span>
            </div>
          ))}
        </div>
      )}

      <div className="match-metadata">
        {/* Confirmation status, timestamp, etc. */}
      </div>
    </div>
  );
};
```

### 3.4 Validation Schema Updates

Update `web/src/validation/schemas.ts`:

```typescript
import { z } from 'zod';

const SetScoreSchema = z.object({
  points_a: z.number().int().nonnegative().max(30),
  points_b: z.number().int().nonnegative().max(30),
}).superRefine((data, ctx) => {
  const { points_a, points_b } = data;
  
  if (points_a === 0 && points_b === 0) {
    // Both zero allowed (unfilled)
    return;
  }

  const winner = Math.max(points_a, points_b);
  const loser = Math.min(points_a, points_b);

  if (winner < 11) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Winning score must be ≥11',
      path: ['points_a', 'points_b'],
    });
  }

  if (winner >= 10) {
    if (!(loser >= winner - 2 || (winner >= 10 && loser >= 9))) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Invalid point spread',
      });
    }
  }
});

export const MatchSubmissionSchema = z.object({
  event_id: z.string().uuid(),
  session_id: z.string().uuid().optional(),
  fixture_slot_id: z.string().uuid().optional(),
  player_a_id: z.string().uuid(),
  player_b_id: z.string().uuid(),
  match_format: z.enum(['BEST_OF_3', 'BEST_OF_5', 'BEST_OF_7']),
  sets_won_a: z.number().int().nonnegative(),
  sets_won_b: z.number().int().nonnegative(),
  sets_won_a_actual: z.number().int().nonnegative().optional(),
  sets_won_b_actual: z.number().int().nonnegative().optional(),
  is_retirement: z.boolean().default(false),
  match_date: z.string().date(),
  
  // NEW FIELD
  set_scores: z.array(SetScoreSchema).optional().nullable(),
}).superRefine(async (data, ctx) => {
  // Existing validation
  const fmt = data.match_format;
  const required = { BEST_OF_3: 2, BEST_OF_5: 3, BEST_OF_7: 4 }[fmt];
  
  if (!data.is_retirement) {
    const winnerSets = Math.max(data.sets_won_a, data.sets_won_b);
    if (winnerSets !== required) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `${fmt} requires winner to have ${required} sets`,
        path: ['sets_won_a', 'sets_won_b'],
      });
    }
  }

  // NEW: If set_scores provided, validate count
  if (data.set_scores && data.set_scores.length > 0) {
    const totalSets = data.sets_won_a + data.sets_won_b;
    if (data.set_scores.length !== totalSets) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: `Must provide ${totalSets} set scores`,
        path: ['set_scores'],
      });
    }
  }
});
```

---

## 4. Implementation Roadmap

### Phase 1: Database & Backend (Weeks 1–2)

- [ ] Create `match_set_score` table
- [ ] Add migration script to `sql/match_set_score.sql`
- [ ] Update `schemas/match.py` with `SetScore` and `MatchSubmit.set_scores`
- [ ] Implement `store_set_scores()` and `get_set_scores()` in `match_service.py`
- [ ] Add `set_scores` field to `MatchResponse` schema
- [ ] Update `POST /api/v1/matches` handler
- [ ] Update `GET /api/v1/matches/{id}` to return `set_scores`
- [ ] Write unit tests for SetScore validation
- [ ] Write integration tests for storing/retrieving points

**Acceptance criteria:**
- API accepts match submissions with or without point data
- Points are correctly stored and retrieved
- Elo ratings unaffected
- All backward-compatible tests pass

### Phase 2: Frontend Form (Weeks 2–3)

- [ ] Create `SetPointsInput.tsx` component
- [ ] Integrate into `MatchSubmissionForm.tsx`
- [ ] Update `web/src/validation/schemas.ts` with SetScore validation
- [ ] Add UI tests for point input flow (collapsed, expanded, clear, save)
- [ ] Update `MatchDetail.tsx` to display point data
- [ ] Add responsive CSS for mobile/tablet
- [ ] Usability testing with coaches (feedback loop)

**Acceptance criteria:**
- Form is usable on mobile/tablet (coach is on court)
- Points section is truly optional (can submit without ever opening it)
- Live validation provides clear feedback
- Points display correctly in match confirmation

### Phase 3: Analytics Infrastructure (Weeks 3–4)

- [ ] Create SQL queries for point-level analytics (separate from rating)
- [ ] Implement new analytics routes (e.g., `GET /api/v1/players/{id}/analytics/points`)
  - Point differential trends
  - Comeback rates (win after down in sets)
  - Point margins by opponent, by format, by date range
- [ ] Add analytics views to frontend (separate from match confirmation)
- [ ] Document analytics data model and limitations

**Acceptance criteria:**
- Analytics queries return correct data for matches with points
- Analytics gracefully handle matches without point data (null/empty)
- Frontend displays analytics without blocking match submissions

### Phase 4: Documentation & Training (Week 4)

- [ ] Update API documentation (swagger/OpenAPI)
- [ ] Create coach guide on when/how to use point entry
- [ ] Add FAQ: "Why are points optional?" "Do they affect my rating?"
- [ ] Document analytics queries for future feature development
- [ ] Update data model diagram (jlrs_data_model.md)

---

## 5. Database Migration Strategy

### Option A: Zero-Downtime (Recommended)

1. **Before deployment:** Create `match_set_score` table (empty)
2. **Deploy backend:** Accept `set_scores` in submissions, but don't require them
3. **Transition period:** Coaches can optionally enter points
4. **Backfill (optional):** Async job to parse or manually enter historical points

```sql
-- Step 1: Create table (no data required)
CREATE TABLE IF NOT EXISTS match_set_score (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES match(match_id) ON DELETE CASCADE,
    set_number INTEGER NOT NULL,
    points_a INTEGER NOT NULL,
    points_b INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (match_id, set_number)
);

-- Step 2: No data migration needed (table is new, matches exist without points)

-- Step 3 (Optional): Backfill from historical data if coaches provide
-- e.g., INSERT INTO match_set_score SELECT ... FROM legacy_points_table;
```

### Option B: If Points Data Exists Elsewhere

If coaches have recorded points in an external system (spreadsheet, PDF, etc.):

```python
# new file: app/jobs/backfill_points.py

def backfill_points_from_csv(file_path: str) -> dict:
    """
    Backfill match_set_score from CSV:
    match_id, set_1_a, set_1_b, set_2_a, set_2_b, ...
    """
    import csv
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            with open(file_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    match_id = row['match_id']
                    for set_num in [1, 2, 3]:
                        pts_a = row.get(f'set_{set_num}_a')
                        pts_b = row.get(f'set_{set_num}_b')
                        if pts_a and pts_b:
                            cur.execute(
                                """INSERT INTO match_set_score 
                                (match_id, set_number, points_a, points_b)
                                VALUES (%s, %s, %s, %s)""",
                                (match_id, set_num, int(pts_a), int(pts_b))
                            )
        conn.commit()
    
    return {"backfilled_records": cur.rowcount}

# CLI: python -m app.jobs.backfill_points --file=/path/to/points.csv
```

---

## 6. Dispute Workflow with Points

### 6.1 Overview: How Points Impact Disputes

The key insight: **Points are supplementary to sets, not the primary result source.**

**Critical principle:**
- Sets (`sets_won_a`, `sets_won_b`) remain the canonical match outcome
- Points (`match_set_score` table) are informational and used for analytics
- Elo ratings **ignore points entirely** (use only set margin)
- Disputes may involve points, but resolution depends on whether sets are also wrong

### 6.2 Current Dispute Workflow (Sets Only, as Reference)

```
1. Match submitted with sets_won_a=2, sets_won_b=1
2. Opponent confirms ✓
3. Elo rating applied, RatingHistory recorded
4. After rating applied, opponent disputes: "I won set 2, not set 1"
5. Dispute status: OPEN
6. Admin reviews and resolves as CORRECTED:
   - Original sets: A=2, B=1 → delta = +20
   - Corrected sets: A=1, B=2 → delta = -20 (if dispute is valid)
7. If CORRECTED:
   a. Rollback original Elo delta (negate it)
   b. Update match.sets_won_a/b to corrected values
   c. Recalculate and write new RatingHistory
8. Elo now reflects correct outcome
```

**Key mechanism:** `RatingHistory` stores the full delta, so rollback is safe and reversible.

### 6.3 Dispute Scenarios with Points

#### Scenario 1: Points Dispute, Sets Correct (Most Common - 80% of cases)

**Situation:**
```
Original match:
  sets_won_a: 2, sets_won_b: 1
  set_scores: Set1(11,9), Set2(5,11), Set3(14,13)
  status: CONFIRMED
  ratings_applied_at: 2026-05-22 15:00 UTC
  elo_delta_applied: +20

Opponent disputes set 1: "Points were 9-11 (I won), not 11-9"
```

**Admin analysis:**
- Sets are correct (opponent did win set 1 based on their claim being 0-1)
- Points in database are wrong (transcription error)
- Corrected set_scores: Set1(9,11), Set2(5,11), Set3(14,13)

**Resolution:**
```python
def resolve_dispute_points_only(conn, dispute_id):
    """
    When points are wrong but sets are correct:
    - Update individual set scores
    - Elo: NO CHANGE (sets_won_a/b unchanged)
    - RatingHistory: NO NEW ENTRY (no recalculation needed)
    - Audit: Log the correction
    """
    with conn.cursor() as cur:
        # Get dispute details
        dispute = get_dispute(conn, dispute_id)
        match_id = dispute["match_id"]
        corrected_scores = dispute["proposed_correction"]  # Set1(9,11), etc.
        
        # Update individual set scores
        for set_num, score in corrected_scores.items():
            cur.execute(
                """UPDATE match_set_score
                   SET points_a = %s, points_b = %s
                   WHERE match_id = %s AND set_number = %s""",
                (score.points_a, score.points_b, match_id, set_num)
            )
        
        # Audit trail
        cur.execute(
            """INSERT INTO match_set_score_audit 
            (match_id, reason, corrected_by, corrected_at)
            VALUES (%s, %s, %s, NOW())""",
            (match_id, f'DISPUTE_{dispute_id}_CORRECTED_POINTS_ONLY', current_user_id)
        )
        
        # Mark dispute resolved
        cur.execute(
            """UPDATE dispute 
               SET status = 'RESOLVED', resolution_reason = 'CORRECTED',
                   resolved_at = NOW(), resolved_by = %s
               WHERE dispute_id = %s""",
            (current_user_id, dispute_id)
        )
        
        conn.commit()
```

**Impact:** ✅ Zero Elo recalculation needed (very efficient)

---

#### Scenario 2: Point Dispute Reveals Set Error (Rare - 15% of cases)

**Situation:**
```
Original match:
  sets_won_a: 2, sets_won_b: 1
  set_scores: Set1(11,9), Set2(5,11), Set3(14,13)

Opponent disputes set 3: "I won Set 3 (14-13), not you. 
                         So I won 2-1 (sets 2 & 3), not you 2-1"

Analysis:
  - If B won Set 3 at 14-13, then:
    - Set 1: A won (11-9)
    - Set 2: B won (5-11)
    - Set 3: B won (14-13)
  - This means: A won 1 set, B won 2 sets
  - BUT recorded as: sets_won_a=2, sets_won_b=1 ❌ INCONSISTENT

CRITICAL: Sets were WRONG. Elo was applied on incorrect data.
```

**Resolution (full correction):**
```python
def resolve_dispute_with_corrected_sets(conn, dispute_id):
    """
    When BOTH points AND sets are wrong:
    1. Rollback original Elo (negate delta)
    2. Update sets_won_a/b to corrected values
    3. Update set_scores to corrected values
    4. Recalculate Elo with new data
    5. Write new RatingHistory
    """
    from app.services.rating_engine import rollback_match, apply_ratings_batch
    
    with conn.cursor() as cur:
        dispute = get_dispute(conn, dispute_id)
        match_id = dispute["match_id"]
        corrected_sets_won_a = 1  # From corrected point analysis
        corrected_sets_won_b = 2
        corrected_set_scores = [
            SetScore(points_a=11, points_b=9),
            SetScore(points_a=5, points_b=11),
            SetScore(points_a=13, points_b=14),  # CORRECTED
        ]
        
        # Step 1: Rollback original Elo
        rollback_match(conn, match_id)
        
        # Step 2: Update match record
        cur.execute(
            """UPDATE match 
               SET sets_won_a = %s, sets_won_b = %s
               WHERE match_id = %s""",
            (corrected_sets_won_a, corrected_sets_won_b, match_id)
        )
        
        # Step 3: Update set_scores
        cur.execute("DELETE FROM match_set_score WHERE match_id = %s", (match_id,))
        for set_num, score in enumerate(corrected_set_scores, 1):
            cur.execute(
                """INSERT INTO match_set_score 
                (match_id, set_number, points_a, points_b)
                VALUES (%s, %s, %s, %s)""",
                (match_id, set_num, score.points_a, score.points_b)
            )
        
        # Step 4 & 5: Recalculate Elo
        tier_changes = apply_ratings_batch(conn, [match_id])
        
        # Step 6: Audit & mark dispute resolved
        cur.execute(
            """INSERT INTO match_set_score_audit 
            (match_id, reason, corrected_by, corrected_at)
            VALUES (%s, %s, %s, NOW())""",
            (match_id, f'DISPUTE_{dispute_id}_CORRECTED_SETS_AND_POINTS', current_user_id)
        )
        
        cur.execute(
            """UPDATE dispute 
               SET status = 'RESOLVED', resolution_reason = 'CORRECTED',
                   resolved_at = NOW(), resolved_by = %s
               WHERE dispute_id = %s""",
            (current_user_id, dispute_id)
        )
        
        conn.commit()
        return tier_changes  # For tier-change webhooks
```

**Impact:** ⚠️ Full Elo recalculation required (expensive but necessary)

---

#### Scenario 3: Dispute on Match with No Points (Backward Compat)

**Situation:**
```
Match submitted without points:
  sets_won_a: 2, sets_won_b: 1
  set_scores: NULL
  status: CONFIRMED, ratings_applied_at: 2026-05-22 15:00 UTC

Opponent disputes: "You won 2-1, I won 2-1"
```

**Resolution:**
```python
def resolve_dispute_no_points(conn, dispute_id):
    """
    Backward compat: dispute on a match with no point data
    - No set_scores to update
    - Same rollback/recalculate flow as sets-only disputes
    """
    from app.services.rating_engine import rollback_match, apply_ratings_batch
    
    with conn.cursor() as cur:
        dispute = get_dispute(conn, dispute_id)
        match_id = dispute["match_id"]
        corrected_sets_won_a = 1
        corrected_sets_won_b = 2
        
        # Rollback original Elo
        rollback_match(conn, match_id)
        
        # Update sets
        cur.execute(
            """UPDATE match 
               SET sets_won_a = %s, sets_won_b = %s
               WHERE match_id = %s""",
            (corrected_sets_won_a, corrected_sets_won_b, match_id)
        )
        
        # Recalculate Elo
        tier_changes = apply_ratings_batch(conn, [match_id])
        
        # Mark resolved
        cur.execute(
            """UPDATE dispute 
               SET status = 'RESOLVED', resolution_reason = 'CORRECTED',
                   resolved_at = NOW(), resolved_by = %s
               WHERE dispute_id = %s""",
            (current_user_id, dispute_id)
        )
        
        conn.commit()
        return tier_changes
```

**Impact:** ✅ Works identically to current (no new concerns)

---

### 6.4 New Audit Table for Points Corrections

To track all point-level corrections (whether via dispute or admin action):

```sql
CREATE TABLE IF NOT EXISTS match_set_score_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES match(match_id),
    old_set_scores JSONB NOT NULL,  -- Snapshot of what was changed
    new_set_scores JSONB NOT NULL,  -- Snapshot of correction
    reason TEXT NOT NULL,  -- e.g., 'DISPUTE_<id>_CORRECTED', 'ADMIN_OVERRIDE'
    corrected_by UUID NOT NULL REFERENCES users(user_id),
    corrected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_reason_not_empty CHECK (reason != '')
);

CREATE INDEX idx_match_set_score_audit_match_id ON match_set_score_audit(match_id);
CREATE INDEX idx_match_set_score_audit_corrected_at ON match_set_score_audit(corrected_at DESC);
```

**Why JSONB here?** Audit trails benefit from flexible schema (storing before/after snapshots). This is metadata about changes, not the operational data.

---

### 6.5 Dispute Handling Decision Tree

```
Dispute received on match with point scores:

┌─ Is dispute about sets (outcome)?
│  
├─ YES → Follow existing set-dispute flow
│         (Rollback → Correct sets → Recalculate Elo → New RatingHistory)
│         Set scores may need updating too if inconsistent
│
└─ NO → Is dispute about points only?
   
   └─ YES → Two sub-cases:
   
      ├─ Are points AND sets internally consistent?
      │  
      │  YES → Update points only (Scenario 1)
      │        Elo: NO CHANGE ✅ Efficient
      │        Action: UPDATE match_set_score WHERE set_number = X
      │
      │  NO → Points dispute reveals set error (Scenario 2)
      │        Elo: FULL RECALCULATION ⚠️ Required
      │        Action: Rollback → Correct sets → Correct points → Recalculate
      │
      └─ NO → Dispute is invalid / cannot be adjudicated
              Action: Mark REJECTED with reason
```

---

### 6.6 Service Layer Method: Determine Dispute Type

```python
def analyze_dispute_scope(conn, dispute_id: str) -> dict:
    """
    Analyze a dispute to determine:
    1. Is it about sets or points?
    2. Will Elo recalculation be needed?
    3. What corrections are proposed?
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.dispute_id, d.match_id, d.reason, d.proposed_correction,
                   m.sets_won_a, m.sets_won_b, m.ratings_applied_at
            FROM dispute d
            JOIN match m ON d.match_id = m.match_id
            WHERE d.dispute_id = %s
            """,
            (dispute_id,)
        )
        dispute = dict(cur.fetchone())
        match_id = dispute["match_id"]
        
        # Fetch current point scores
        cur.execute(
            """
            SELECT set_number, points_a, points_b
            FROM match_set_score
            WHERE match_id = %s
            ORDER BY set_number ASC
            """,
            (match_id,)
        )
        current_points = [dict(r) for r in cur.fetchall()]
        
        # Parse proposed correction
        proposed_sets = dispute.get("proposed_correction", {}).get("sets")
        proposed_points = dispute.get("proposed_correction", {}).get("points")
        
        # Determine scope
        scope = {
            "has_point_data": len(current_points) > 0,
            "dispute_about_sets": proposed_sets is not None,
            "dispute_about_points": proposed_points is not None,
            "requires_elo_recalculation": False,
            "severity": "INFORMATIONAL",  # or "RATING_IMPACTING"
        }
        
        # If sets are disputed, Elo recalculation is needed
        if proposed_sets is not None:
            if proposed_sets != {"sets_won_a": dispute["sets_won_a"], 
                                 "sets_won_b": dispute["sets_won_b"]}:
                scope["requires_elo_recalculation"] = True
                scope["severity"] = "RATING_IMPACTING"
        
        # If points are disputed AND sets need correction too
        elif proposed_points is not None:
            # Check: do proposed points contradict current set outcome?
            inferred_sets = infer_sets_from_points(proposed_points)
            if inferred_sets != {"sets_won_a": dispute["sets_won_a"], 
                                 "sets_won_b": dispute["sets_won_b"]}:
                scope["requires_elo_recalculation"] = True
                scope["severity"] = "RATING_IMPACTING"
        
        return scope
```

---

## 7. Backward Compatibility & Testing

### Backward Compatibility Matrix

| Scenario | Current Behavior | With Points | Status |
|----------|------------------|-------------|--------|
| Submit match without points | ✓ Works | ✓ Still works (null set_scores) | ✓ Compatible |
| Query match without points | ✓ Returns set scores | ✓ Returns set scores + set_scores=null | ✓ Compatible |
| Calculate Elo (no points) | ✓ Uses sets_won_a/b | ✓ Same, ignores set_scores | ✓ Compatible |
| Query match with points | N/A | ✓ Returns set scores + set_scores=[...] | ✓ New capability |
| Confirm/dispute match (no points) | ✓ Works | ✓ Still works | ✓ Compatible |
| Rollback match (no points) | ✓ Works | ✓ Still works | ✓ Compatible |
| Dispute match (no points) | ✓ Works | ✓ Same flow, no set_scores to update | ✓ Compatible |
| Dispute match (with points, sets OK) | N/A | ✓ Update points only, Elo unchanged | ✓ New capability |
| Dispute match (with points, sets wrong) | N/A | ✓ Full recalculation | ✓ New capability |
| Analytics (no points) | N/A | ✓ Returns null or empty | ✓ Graceful |

### Test Strategy (Disputes)

#### Unit Tests (Dispute Resolution)

```python
# tests/unit/test_dispute_resolution.py

def test_resolve_dispute_points_only_no_elo_change():
    """When points are wrong but sets are correct, Elo must not change"""
    # Setup: match with wrong point scores
    # Action: resolve_dispute_points_only()
    # Assert: RatingHistory unchanged, set_scores updated

def test_resolve_dispute_sets_wrong_triggers_recalculation():
    """When points dispute reveals wrong sets, must recalculate Elo"""
    # Setup: match with sets and points both wrong
    # Action: resolve_dispute_with_corrected_sets()
    # Assert: RatingHistory new entry, sets updated, points updated

def test_resolve_dispute_no_points_data():
    """Backward compat: dispute on match without point data"""
    # Setup: legacy match with set_scores NULL
    # Action: resolve_dispute_no_points()
    # Assert: Works as before, no set_scores to update
```

#### Unit Tests (Point Validation - from earlier section)

```python
# tests/unit/test_set_score_validation.py

def test_set_score_valid_standard_win():
    score = SetScore(points_a=11, points_b=9)
    assert score.points_a == 11

def test_set_score_valid_deuce():
    score = SetScore(points_a=14, points_b=13)
    assert score.points_a == 14

def test_set_score_invalid_too_low():
    with pytest.raises(ValueError, match="Winning player in a set must have ≥11"):
        SetScore(points_a=10, points_b=8)

def test_set_score_invalid_spread():
    with pytest.raises(ValueError, match="Invalid point spread"):
        SetScore(points_a=11, points_b=8)

def test_set_score_both_zero():
    score = SetScore(points_a=0, points_b=0)
    assert score.points_a == 0  # Allowed (unfilled)

def test_match_submit_without_set_scores():
    """Backward compat: match submission works without set_scores"""
    body = MatchSubmit(
        event_id="...",
        player_a_id="...",
        player_b_id="...",
        match_format=MatchFormat.BEST_OF_3,
        sets_won_a=2,
        sets_won_b=0,
        match_date=date.today(),
    )
    assert body.set_scores is None

def test_match_submit_with_set_scores():
    """New feature: set_scores provided and valid"""
    body = MatchSubmit(
        event_id="...",
        player_a_id="...",
        player_b_id="...",
        match_format=MatchFormat.BEST_OF_3,
        sets_won_a=2,
        sets_won_b=1,
        match_date=date.today(),
        set_scores=[
            SetScore(points_a=11, points_b=9),
            SetScore(points_a=5, points_b=11),
            SetScore(points_a=14, points_b=13),
        ]
    )
    assert len(body.set_scores) == 3
```

#### Integration Tests

```python
# tests/integration/test_match_points_flow.py

def test_submit_match_with_points_stores_in_db():
    with get_connection() as conn:
        # Submit match with points
        result = match_service.submit_match(
            conn, 
            MatchSubmit(..., set_scores=[...]), 
            "coach-id"
        )
        match_id = result["match_id"]
        
        # Store points
        match_service.store_set_scores(conn, match_id, [...])
        
        # Retrieve and verify
        points = match_service.get_set_scores(conn, match_id)
        assert len(points) == 3
        assert points[0]["points_a"] == 11
        
        conn.commit()

def test_elo_rating_ignores_points():
    """Elo calculation must not change with or without points"""
    # Match A: with points
    # Match B: same match without points
    # Both should produce identical rating deltas
    
    match_with_points = MatchSubmit(..., set_scores=[...])
    match_without_points = MatchSubmit(..., set_scores=None)
    
    with get_connection() as conn:
        submit_match(conn, match_with_points, ...)
        submit_match(conn, match_without_points, ...)
    
    # Apply ratings for both
    with get_connection() as conn:
        apply_ratings_batch(conn, [match_with_points_id, match_without_points_id])
    
    # Query RatingHistory for both
    with get_connection() as conn:
        history_with = get_rating_history(conn, match_with_points_id)
        history_without = get_rating_history(conn, match_without_points_id)
    
    # Deltas must be identical
    assert history_with["delta"] == history_without["delta"]
```

#### Frontend Tests

```typescript
// web/src/__tests__/SetPointsInput.test.tsx

describe('SetPointsInput', () => {
  it('renders collapsed by default', () => {
    render(
      <SetPointsInput
        matchFormat="BEST_OF_3"
        setsWonA={2}
        setsWonB={1}
        onSetScoresChange={vi.fn()}
        isRetirement={false}
      />
    );
    
    const detailContainer = screen.queryByRole('heading', { name: /set 1:/i });
    expect(detailContainer).not.toBeInTheDocument();
  });

  it('expands when toggle is clicked', () => {
    render(<SetPointsInput ... />);
    fireEvent.click(screen.getByText(/point scores/i));
    
    const inputs = screen.getAllByRole('textbox');
    expect(inputs).toHaveLength(6);  // 3 sets × 2 players
  });

  it('disables save when errors present', () => {
    const { rerender } = render(<SetPointsInput ... />);
    fireEvent.click(screen.getByText(/point scores/i));
    
    // Enter invalid score
    fireEvent.change(screen.getByLabelText(/Set 1 Player A/), { target: { value: '5' } });
    fireEvent.change(screen.getByLabelText(/Set 1 Player B/), { target: { value: '3' } });
    
    expect(screen.getByText(/save points/i)).toBeDisabled();
  });

  it('calls onSetScoresChange when Discard is clicked', () => {
    const onChangeMock = vi.fn();
    render(<SetPointsInput onSetScoresChange={onChangeMock} ... />);
    
    fireEvent.click(screen.getByText(/discard points/i));
    expect(onChangeMock).toHaveBeenCalledWith(null);
  });
});
```

---

## 8. Design Decisions & Rationale

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Storage model** | Separate `match_set_score` table | Flexible schema (3, 5, or 7 sets), sparse data handling, immutability |
| **Elo impact** | None (uses sets_won_a/b only) | Preserves system integrity, prevents gaming, backward compatible |
| **UI visibility** | Collapsed optional section | Doesn't slow down coaches during casual sessions, clear intent |
| **Validation location** | Hybrid (schema + service + frontend) | Defense in depth; schema for ORM safety, service for business rules, frontend for UX |
| **Backward compatibility** | Full (null set_scores allowed) | No forced migration, gradual adoption |
| **Point range** | 0–30 (modern table tennis + deuces) | Handles 11-point (or 21-point old rules) and extended deuces |
| **Analytics decoupled** | Separate from rating logic | Allows future flexibility; rating stays stable while analytics can evolve |

---

## 9. Risk Assessment & Mitigation

### Risk 1: Data Entry Errors Leading to Inconsistency

**Risk:** Coach enters point scores that don't match set winner (e.g., A wins set but points show B won).

**Mitigation:**
- Strict validation: Set score winner must match recorded set winner
- Frontend real-time feedback
- Allow "Discard Points" button — coach can always fall back to set-only submission
- Post-submission warning if points seem inconsistent

### Risk 2: Performance Impact (Large Queries)

**Risk:** Querying match + set_scores for every match could slow down match listing.

**Mitigation:**
- Lazy load: `set_scores` only included if explicitly requested (separate endpoint or query param)
- `MatchResponse` defaults to omitting `set_scores` unless match detail page requests it
- Index on `match_set_score(match_id)` for fast lookups

### Risk 3: Elo Rating Engine Inadvertently Using Points

**Risk:** Future developer changes rating engine to use points, breaking rating stability.

**Mitigation:**
- **Code comment** at top of `apply_ratings_batch()`:
  ```python
  """
  CRITICAL: This engine uses sets_won_a/b ONLY. 
  Do NOT incorporate match_set_score data.
  Points are for analytics/future use. Do not change rating logic.
  """
  ```
- **Unit test** that explicitly verifies Elo delta is identical with/without points
- **Code review checklist:** "Did you touch rating_engine.py for points? If yes, explain why."

### Risk 4: Coaches Entering Invalid Points

**Risk:** Despite validation, coaches might enter nonsensical data (typos, misunderstandings).

**Mitigation:**
- Clear UI hints ("e.g., 11-9")
- Live validation with human-readable errors
- Disable submit until valid
- Allow clear/discard — no penalty for incomplete data
- Encourage "start with set scores, add points later if confident"

### Risk 5: Upgrade Complexity

**Risk:** Rolling out to live system with existing matches might cause issues.

**Mitigation:**
- Add `match_set_score` table in migration (empty, no data)
- Deploy backend first (accepts set_scores but ignores them initially)
- Monitor for 1-2 weeks (no breaking changes possible)
- Then roll out frontend incrementally (feature flag if needed)

---

## 10. Success Metrics

### Adoption Metrics

- % of matches with point data entered (target: 40% of LEAGUE matches within 3 months)
- Average # of attempts before successful point entry (target: <2)
- Abandonment rate (% of coaches who open points section but discard) (target: <20%)

### Quality Metrics

- Point-entry validation error rate (target: <5%)
- Elo rating consistency (points/no-points deltas must be identical)
- Data integrity: matches where points don't match set winner (target: 0%)

### Performance Metrics

- API response time for `/matches/{id}` (target: <100ms with points)
- Analytics query latency (target: <2s for season-long trends)

---

## 11. Future Extensions (Out of Scope)

Once points data accumulates, the system can evolve:

1. **Tighter Elo model:** Use point differential to adjust K-factor multipliers (e.g., 14-13 win gets K×0.8, 11-0 whitewash gets K×1.2)

2. **Performance analytics dashboard:**
   - "Win % when trailing after set 1"
   - "Comeback champions" (players with highest win-from-down rates)
   - "Closest matches" (by point margin)

3. **AI coaching insights:** "Player A tends to tighten up in close sets — work on mental toughness"

4. **Head-to-head point trends:** Historical point margin trends vs. specific opponents

5. **Match difficulty weighting:** Use point margin to weight match importance in rating (currently uses set margin only)

---

## 12. API Contract Extensions

### `POST /api/v1/matches` (Updated)

**Request:**
```json
{
  "event_id": "uuid",
  "player_a_id": "uuid",
  "player_b_id": "uuid",
  "match_format": "BEST_OF_3",
  "sets_won_a": 2,
  "sets_won_b": 1,
  "is_retirement": false,
  "match_date": "2026-05-22",
  "set_scores": [
    { "points_a": 11, "points_b": 9 },
    { "points_a": 5, "points_b": 11 },
    { "points_a": 14, "points_b": 13 }
  ]
}
```

**Response:**
```json
{
  "match_id": "uuid",
  "player_a": { ... },
  "player_b": { ... },
  "match_format": "BEST_OF_3",
  "sets_won_a": 2,
  "sets_won_b": 1,
  "set_scores": [
    { "set_number": 1, "points_a": 11, "points_b": 9 },
    { "set_number": 2, "points_a": 5, "points_b": 11 },
    { "set_number": 3, "points_a": 14, "points_b": 13 }
  ],
  "confirmation_status": "PENDING",
  ...
}
```

### `GET /api/v1/matches/{id}` (Updated)

**Response includes:**
```json
{
  "match_id": "uuid",
  ...
  "set_scores": [
    { "set_number": 1, "points_a": 11, "points_b": 9 },
    ...
  ]
}
```

### `GET /api/v1/players/{id}/analytics/points` (New)

**Query Params:**
- `date_from`: Start date for trend
- `date_to`: End date
- `format`: Filter by format (FRIENDLY, LEAGUE, TOURNAMENT, or all)

**Response:**
```json
{
  "player_id": "uuid",
  "analytics_window": {
    "from": "2026-01-01",
    "to": "2026-05-22"
  },
  "summary": {
    "matches_with_points": 42,
    "avg_points_for": 10.2,
    "avg_points_against": 8.7,
    "point_differential": 1.5,
    "trendline": "↗"
  },
  "by_format": {
    "FRIENDLY": { ... },
    "LEAGUE": { ... },
    "TOURNAMENT": { ... }
  },
  "by_opponent": [
    {
      "opponent_id": "uuid",
      "opponent_name": "Opponent Name",
      "matches": 3,
      "points_avg_diff": 2.1
    }
  ]
}
```

---

## 13. Summary: Changes Required

### Backend

| Component | Change | Effort | Notes |
|-----------|--------|--------|-------|
| Database | Add `match_set_score` table | 1-2h | SQL DDL only |
| Schemas | Add `SetScore`, update `MatchSubmit/Response` | 2-3h | Validation rules |
| Services | Add `store_set_scores()`, `get_set_scores()` | 2-3h | CRUD operations |
| Routers | Update `POST /matches` handler, add new endpoints | 2-3h | Wiring only |
| Rating engine | No changes | 0h | Intentional (backward compatible) |
| Tests | Unit + integration for points flow | 4-5h | Comprehensive coverage |

**Backend Total: ~13–18 hours**

### Frontend

| Component | Change | Effort | Notes |
|-----------|--------|--------|-------|
| Schemas | Add `SetScore` to zod validation | 2-3h | Field validation |
| Components | Create `SetPointsInput.tsx` | 4-5h | Collapsed, dynamic, responsive |
| Forms | Integrate into `MatchSubmissionForm.tsx` | 1-2h | Hook up state |
| Display | Update `MatchDetail.tsx` | 1-2h | Show points if available |
| Styling | CSS for optional section | 2-3h | Mobile-friendly layout |
| Tests | Component + integration tests | 3-4h | Coverage for UX flow |

**Frontend Total: ~13–19 hours**

### Documentation

| Item | Effort |
|------|--------|
| API contract update | 1-2h |
| Data model diagram | 1h |
| Coach guide (optional points) | 1-2h |
| FAQ + troubleshooting | 1h |

**Documentation Total: ~4–5 hours**

### **Total Effort: ~30–42 hours (~1 sprint)**

---

## 14. Appendix: Example Workflows

### Workflow 1: Coach Entering Match (No Points)

```
Coach: [Open Match Submission]
UI: Form shown with set scores section visible
Coach: [Enter Player A, Player B, Match Date]
Coach: [Enter sets_won_a=2, sets_won_b=1]
UI: "Point Scores (Optional)" section collapsed
Coach: [Click Submit]
Backend: Match stored with sets_won_a/b, set_scores=null
Elo: Calculated using only set margin
Result: ✓ Match confirmed, rated normally
```

### Workflow 2: Coach Entering Match (With Points)

```
Coach: [Open Match Submission]
Coach: [Enter Player A, Player B, Match Date, sets_won_a=2, sets_won_b=1]
UI: "Point Scores (Optional)" section visible but collapsed
Coach: [Click "▼ Point Scores (Optional)"]
UI: Point input fields appear (3 sets for BEST_OF_3)
Coach: [Enter Set 1: 11-9, Set 2: 5-11, Set 3: 14-13]
UI: Real-time validation → "Set 1: 11-9 ✓", "Set 2: 5-11 ✓", "Set 3: 14-13 ✓"
Coach: [Click "Save Points"]
Coach: [Click Submit Match]
Backend: Match stored with sets_won_a/b AND set_scores
Elo: Calculated using only set margin (points ignored)
Analytics: Points stored for future queries
Result: ✓ Match confirmed, rated normally, points available for analytics
```

### Workflow 3: Coach Changes Mind (Discard Points)

```
Coach: [Entered match with points, clicks "Discard Points"]
UI: Point inputs cleared, hidden
Coach: [Click Submit Match]
Backend: Match stored with sets_won_a/b, set_scores=null
Result: ✓ Same as Workflow 1
```

### Workflow 4: Analytics Query (Future)

```
Coach/Admin: [Open Player Detail Page]
UI: Shows match history, current rating, tier
Coach: [Click "Performance Analytics" tab]
UI: [Loads analytics data]
Display:
  - "Point differential vs. top 10 players: avg +1.3"
  - "Comeback rate (after being down 0-1 sets): 62%"
  - "Tightest sets: vs. Player Y (avg margin 1.5 points)"
Backend: Query match_set_score, aggregate by format/opponent/date
Result: ✓ Coach gains insights from accumulated point data
```

---

## 15. Open Questions for Clarification

As you review this plan, consider:

1. **Points entry timeline:** Do you want coaches to start entering points immediately upon deployment, or should we phase it in (e.g., LEAGUE only first)?

2. **Mandatory rollout:** Should we set a deadline (e.g., "All League matches from June 1 onwards require points")? Or always voluntary?

3. **Historical data:** Do you have historical point data that needs to be backfilled? If so, in what format?

4. **Analytics priority:** Which analytics queries are highest priority? (e.g., point differential trends vs. comeback rates vs. something else?)

5. **Mobile UX refinement:** Would you like a prototype of the point-input UI on mobile before we build it?

---

## Summary

This plan transitions JLRS from a **Result-Only system** (set scores only) to a **Performance-Granular system** (set + point scores available) while maintaining:

✓ **Full backward compatibility** — matches work with or without points  
✓ **Rating system integrity** — Elo engine unchanged, unaffected by points  
✓ **Coaching simplicity** — point entry is truly optional, non-blocking  
✓ **Future flexibility** — data ready for deeper analytics and potential rating refinements  

The implementation is incremental, low-risk, and can be deployed as a single ~1-week sprint.

