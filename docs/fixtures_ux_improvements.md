# Fixtures UI/UX Improvements Proposal

## Current Issues

1. **Strategy dropdown shows wrong value after generation**
   - After selecting "Team Match Format" and generating, dropdown reverts to "Tier Match Cross Academy"
   - Root cause: UI state not updated with actual generated strategy

2. **Regenerate allowed with existing match results**
   - Button stays enabled even after matches are created from fixtures
   - Foreign key constraint failures when trying to delete fixture slots with matches
   - Poor error messaging to user

3. **Players can be registered/withdrawn after fixtures generated**
   - No roster lock mechanism
   - Breaks fixture generation assumptions (fixed player count per academy)
   - Should be prevented at UI + API level

4. **No way to apply ratings after results entered**
   - Match results can be submitted, but ratings don't update
   - No "Apply Ratings" or "Save Results" button
   - Players' current_rating stays unchanged

---

## Proposed Solution

### 1. Fixture Lifecycle State Management

Create a **fixture_state** tracking mechanism (separate from event.status):

```
ROSTER_OPEN (initial state)
  ↓
FIXTURES_READY (after generation - roster locked, fixtures can be regenerated)
  ↓
FIXTURE_FROZEN (coach locks in fixtures - no more regeneration allowed)
  ↓
RESULTS_SUBMITTED (once all results entered)
  ↓
RATINGS_APPLIED (after rating calculation)
```

**Add to event table:**
```sql
ALTER TABLE event ADD COLUMN fixture_state VARCHAR(50) DEFAULT NULL;
-- NULL for INTRA_ACADEMY events (they use sessions, not league fixtures)
-- ROSTER_OPEN for INTER_ACADEMY LEAGUE events
```

**Fixture State Enum Values:**
- `ROSTER_OPEN` - Initial state, players can be registered/withdrawn, no fixtures generated
- `FIXTURES_READY` - Fixtures generated, roster locked (can't add/remove players), can regenerate
- `FIXTURE_FROZEN` - Coach locked fixtures, no more regeneration allowed, roster still locked
- `RESULTS_SUBMITTED` - All match results entered, ready to apply ratings
- `RATINGS_APPLIED` - Ratings updated, event complete

### 2. Fix Strategy Dropdown

**Frontend (Admin.tsx / Fixtures UI):**
- Store `selectedStrategy` in component state
- After successful generation API call, update state with response's `fixture_strategy`
- Populate dropdown value from state: `value={selectedStrategy}`
- Disable dropdown once `fixture_state === 'FIXTURES_READY'`

**Backend API Response:**
- Already returns `fixture_strategy` in `EventFixturesResponse` ✓
- No change needed

**Code example:**
```typescript
// Before
const [strategy, setStrategy] = useState("TIER_MATCHED");

// After
const [selectedStrategy, setSelectedStrategy] = useState("TIER_MATCHED");

// On generation success:
const response = await generateFixtures();
setSelectedStrategy(response.fixture_strategy);  // <-- Update state
```

### 3. Prevent Regenerate When Fixtures Frozen

**Key Behavior:**
- ✓ Regenerate ALLOWED when `fixture_state = 'FIXTURES_READY'` (coaching flexibility)
- ✗ Regenerate DISABLED when `fixture_state = 'FIXTURE_FROZEN'` (locked in choice)
- ✗ Regenerate DISABLED when matches exist (FK constraint protection)

**Backend Validation (app/routers/events.py):**

Before accepting regeneration request, check:
```python
# Check fixture state
cur.execute("""
    SELECT fixture_state FROM event WHERE event_id = %s
""", (event_id,))
state = cur.fetchone()['fixture_state']

if state == 'FIXTURE_FROZEN':
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Cannot regenerate fixtures: fixtures have been frozen by coach. "
               "Unfreeze fixtures to allow changes."
    )

if state == 'RATINGS_APPLIED':
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Cannot regenerate fixtures: event is complete with ratings applied."
    )

# Also check if any fixture slots have associated matches
cur.execute("""
    SELECT COUNT(*) FROM event_fixture_slot efs
    WHERE efs.event_id = %s AND efs.match_id IS NOT NULL
""", (event_id,))
match_count = cur.fetchone()[0]

if match_count > 0:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Cannot regenerate fixtures: {match_count} matches already created. "
               "Clear match results first or create a new event."
    )

# On successful regeneration, set state to FIXTURES_READY
cur.execute("""
    UPDATE event SET fixture_state = 'FIXTURES_READY' WHERE event_id = %s
""", (event_id,))
```

**Frontend:**

1. Query endpoint to get current fixture state and check if regenerate is allowed:
   ```typescript
   GET /events/{event_id}/fixtures/status
   // Returns: { 
   //   fixture_state: 'ROSTER_OPEN' | 'FIXTURES_READY' | 'FIXTURE_FROZEN' | ... 
   //   can_regenerate: boolean, 
   //   reason?: string 
   // }
   ```

2. Regenerate button states:
   ```typescript
   // ROSTER_OPEN: hidden (no fixtures to regenerate)
   // FIXTURES_READY: enabled with warning
   // FIXTURE_FROZEN: disabled with message "Frozen - unlock to regenerate"
   // RATINGS_APPLIED: disabled with message "Event complete"
   
   <button 
     onClick={handleRegenerate} 
     disabled={!canRegenerate}
     title={getRegenerateTooltip()}
   >
     🔄 Regenerate Fixtures
   </button>
   ```

3. Show confirmation dialog when regenerating (state = FIXTURES_READY):
   ```
   "Regenerate fixtures? This will delete current pairings and generate new ones.
    Coach review will be required. Players must re-enter match results."
   ```

### 4. Lock Roster After Fixtures Generated (FIXTURES_READY State)

**Roster Lock Behavior:**
- ✓ Players can be added/removed when `fixture_state = 'ROSTER_OPEN'`
- ✗ Players CANNOT be added/removed when `fixture_state = 'FIXTURES_READY'` or later
- Roster stays locked through FIXTURE_FROZEN state (fixtures are still locked)
- Roster stays locked through RESULTS_SUBMITTED → RATINGS_APPLIED

**Backend (app/services/event_player_service.py):**

In `register_player()` and `remove_player()`, add check:
```python
# Check if event has fixtures already generated
cur.execute("""
    SELECT fixture_state FROM event WHERE event_id = %s
""", (event_id,))
event = cur.fetchone()
state = event['fixture_state'] if event else None

if state and state != 'ROSTER_OPEN':
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Cannot modify roster: fixtures have been generated ({state}). "
               f"Regenerate fixtures to add/remove players."
    )
```

**Frontend:**

1. Show roster status message:
   ```typescript
   {fixtureState !== 'ROSTER_OPEN' && (
     <div className="info-message roster-locked">
       🔒 Roster is locked (fixtures generated)
     </div>
   )}
   ```

2. Hide/disable register/withdraw buttons after fixtures generated:
   ```typescript
   {fixtureState === 'ROSTER_OPEN' && (
     <div className="roster-actions">
       <button onClick={handleRegisterPlayer}>+ Register Player</button>
       {/* Withdraw buttons in player list */}
     </div>
   )}
   ```

3. Show helpful message if coach tries to modify:
   ```typescript
   <DisabledTooltip message="Roster locked after fixture generation. Regenerate to modify.">
     <button disabled>+ Register Player</button>
   </DisabledTooltip>
   ```

### 5. Add "Lock Fixture" Button (Coach Flexibility)

**Purpose:** Allow coaches to try different fixture strategies before locking in their choice.

**Behavior:**
- Only visible when `fixture_state = 'FIXTURES_READY'`
- Clicking locks fixtures and prevents regeneration
- Sets `fixture_state = 'FIXTURE_FROZEN'`
- Shows confirmation: "Lock these fixtures? You won't be able to regenerate or modify."

**Backend Endpoint:**

```python
@router.post("/{event_id}/fixtures/lock")
def lock_fixtures(
    event_id: str,
    current_user: dict = Depends(require_roles("ADMIN", "COACH"))
):
    """Lock fixtures - prevents regeneration and roster changes"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT fixture_state, host_academy_id FROM event WHERE event_id = %s
            """, (event_id,))
            event = cur.fetchone()
            
            if not event:
                raise HTTPException(status_code=404, detail="Event not found")
            
            if event['fixture_state'] != 'FIXTURES_READY':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot lock fixtures in {event['fixture_state']} state. "
                           "Only FIXTURES_READY fixtures can be locked."
                )
            
            # Check authorization
            if current_user["role"] == "COACH":
                if current_user["academy_id"] != event['host_academy_id']:
                    raise HTTPException(status_code=403, detail="Only host coach can lock")
            
            cur.execute("""
                UPDATE event SET fixture_state = 'FIXTURE_FROZEN' WHERE event_id = %s
            """, (event_id,))
            conn.commit()
    
    return {"success": True, "fixture_state": "FIXTURE_FROZEN"}
```

**Frontend:**

```typescript
{fixtureState === 'FIXTURES_READY' && (
  <div className="fixture-review-section">
    <h3>📋 Review & Lock Fixtures</h3>
    <p>Try different fixture strategies before locking in your choice.</p>
    
    <div className="button-group">
      <button onClick={handleRegenerate} className="btn-secondary">
        🔄 Regenerate with Different Strategy
      </button>
      
      <button onClick={handleLockFixtures} className="btn-primary">
        🔒 Lock These Fixtures
      </button>
    </div>
    
    <ConfirmDialog
      title="Lock Fixtures?"
      message="Once locked, you cannot regenerate or modify fixtures. Match results can still be entered."
      onConfirm={confirmLockFixtures}
      confirmText="Lock"
    />
  </div>
)}

{fixtureState === 'FIXTURE_FROZEN' && (
  <div className="success-banner">
    ✓ Fixtures locked - no further changes allowed
  </div>
)}
```

**New Backend Endpoint:**

```python
@router.post("/{event_id}/apply-ratings")
def apply_event_ratings(
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Apply ELO rating updates from all completed matches in this event.
    - Updates player.current_rating
    - Creates rating_history entries
    - Sets match.ratings_applied_at timestamp
    - Moves fixture_state to RATINGS_APPLIED
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Fetch all matches with results
            cur.execute("""
                SELECT m.*, fs.match_category
                FROM match m
                LEFT JOIN event_fixture_slot fs ON m.fixture_slot_id = fs.slot_id
                WHERE m.event_id = %s
                  AND m.confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')
                  AND m.ratings_applied_at IS NULL
                  AND m.rating_eligible = true
            """, (event_id,))
            matches = [dict(r) for r in cur.fetchall()]
            
            # Calculate rating updates using rating_engine
            updates = []
            for match in matches:
                # Call rating_engine.calculate_elo_change()
                rating_change_a, rating_change_b = calculate_elo_change(
                    player_a_rating=match['player_a_rating'],
                    player_b_rating=match['player_b_rating'],
                    match_category=match['match_category'],
                    winner_id=match['winner_id'],
                    is_cross_academy=match['player_a_academy_id'] != match['player_b_academy_id']
                )
                updates.append({
                    'match_id': match['match_id'],
                    'player_a_id': match['player_a_id'],
                    'player_b_id': match['player_b_id'],
                    'rating_change_a': rating_change_a,
                    'rating_change_b': rating_change_b,
                    'new_rating_a': match['player_a_rating'] + rating_change_a,
                    'new_rating_b': match['player_b_rating'] + rating_change_b,
                })
            
            # Apply updates atomically
            for update in updates:
                # Update player ratings
                cur.execute("""
                    UPDATE player SET current_rating = %s 
                    WHERE player_id = %s
                """, (update['new_rating_a'], update['player_a_id']))
                
                # Create rating history
                cur.execute("""
                    INSERT INTO rating_history (...)
                    VALUES (...)
                """)
                
                # Mark match ratings as applied
                cur.execute("""
                    UPDATE match SET ratings_applied_at = NOW()
                    WHERE match_id = %s
                """, (update['match_id'],))
            
            conn.commit()
            
            # Update fixture_state to RATINGS_APPLIED
            cur.execute("""
                UPDATE event SET fixture_state = 'RATINGS_APPLIED'
                WHERE event_id = %s
            """, (event_id,))
            conn.commit()
    
    return {
        "success": True,
        "matches_processed": len(matches),
        "updates": updates,
        "fixture_state": "RATINGS_APPLIED"
    }
```

**Frontend:**

1. Show "Apply Ratings" button ONLY after all results submitted (fixture_state = RESULTS_SUBMITTED):
   ```typescript
   {fixtureState === 'RESULTS_SUBMITTED' && (
     <button 
       onClick={handleApplyRatings}
       className="btn-primary btn-large"
     >
       ✅ Apply Ratings
     </button>
   )}
   
   {fixtureState !== 'RESULTS_SUBMITTED' && (
     <button disabled title="Enter all match results first">
       Apply Ratings
     </button>
   )}
   ```

2. Show rating change summary before applying:
   ```typescript
   <RatingChangeSummary updates={ratingUpdates} />
   // Shows each player's change:
   // Player A: 1200 → 1215 (+15)
   // Player B: 1180 → 1165 (-15)
   ```

3. Lock UI after ratings applied:
   ```typescript
   {fixtureState === 'RATINGS_APPLIED' && (
     <div className="success-banner">
       ✓ Event complete - Ratings applied for {updateCount} matches
       <button onClick={handleDownloadReport}>📊 Download Report</button>
     </div>
   )}
   ```

---

## Implementation Priority

**Phase 1 (High Priority - UI only):**
1. Fix strategy dropdown state management ✓ Easy
2. Add "can-regenerate" check endpoint and disable button
3. Add roster lock prevention on UI (disable buttons)

**Phase 2 (Medium Priority - Backend validation):**
4. Add fixture_state tracking to event table
5. Add backend validation for roster lock
6. Add backend validation for regenerate with matches

**Phase 3 (High Value - New Feature):**
7. Implement Apply Ratings endpoint
8. Add rating change summary UI

---

## Database Schema Changes Needed

```sql
-- Add fixture_state to event table (NULL for INTRA_ACADEMY)
ALTER TABLE event ADD COLUMN fixture_state VARCHAR(50) DEFAULT NULL;

-- Create enum for better type safety
DO $$ BEGIN
    CREATE TYPE fixture_lifecycle_state AS ENUM (
        'ROSTER_OPEN',
        'FIXTURES_READY',
        'FIXTURE_FROZEN',
        'RESULTS_SUBMITTED',
        'RATINGS_APPLIED'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Update event table to use enum
ALTER TABLE event MODIFY COLUMN fixture_state fixture_lifecycle_state;
```

**State Transitions:**
- INTER_ACADEMY LEAGUE events: NULL → ROSTER_OPEN (on creation)
- INTRA_ACADEMY events: always NULL (use sessions instead)
- Transitions: ROSTER_OPEN → FIXTURES_READY (generate) → FIXTURE_FROZEN (lock) → RESULTS_SUBMITTED (all results) → RATINGS_APPLIED (ratings applied)

---

## Summary: Fixture State Lifecycle & Button Behavior

| State | Fixture Generation | Regenerate Button | Lock Button | Register/Withdraw | Apply Ratings | Description |
|-------|-------------------|------------------|------------|-------------------|---------------|-------------|
| ROSTER_OPEN | ✓ Enabled | ✗ Hidden | ✗ Hidden | ✓ Enabled | ✗ Disabled | Initial state - build roster |
| FIXTURES_READY | ✓ Enabled | ✓ Enabled | ✓ Enabled | ✗ Locked | ✗ Disabled | Fixtures generated - coach reviews |
| FIXTURE_FROZEN | ✗ Disabled | ✗ Disabled | ✗ Hidden | ✗ Locked | ✗ Disabled | Locked in - waiting for results |
| RESULTS_SUBMITTED | ✗ Disabled | ✗ Disabled | ✗ Hidden | ✗ Locked | ✓ Enabled | All results entered - ready to apply |
| RATINGS_APPLIED | ✗ Disabled | ✗ Disabled | ✗ Hidden | ✗ Locked | ✗ Complete | Event done - ratings updated |

---

## User Workflows

### Workflow 1: Coach Reviews Multiple Fixture Strategies
```
ROSTER_OPEN
  ↓ Generate fixtures with TIER_MATCHED
FIXTURES_READY (review pairings)
  ↓ Click "Regenerate with Different Strategy"
FIXTURES_READY (now with TEAM_FORMAT)
  ↓ Click "Regenerate with Different Strategy"
FIXTURES_READY (now with CROSS_ACADEMY_ONLY)
  ↓ Satisfied - Click "Lock These Fixtures"
FIXTURE_FROZEN (no more changes allowed)
  ↓ Match results entered
RESULTS_SUBMITTED
  ↓ Click "Apply Ratings"
RATINGS_APPLIED (event complete)
```

### Workflow 2: Generate Once and Lock
```
ROSTER_OPEN
  ↓ Register all players
  ↓ Generate fixtures with default TIER_MATCHED
FIXTURES_READY
  ↓ Immediately click "Lock These Fixtures"
FIXTURE_FROZEN
  ↓ Match results entered
RESULTS_SUBMITTED
  ↓ Click "Apply Ratings"
RATINGS_APPLIED
```

### Workflow 3: Attempted Invalid Actions (Blocked)
```
FIXTURES_READY
  ↓ Try to register new player → ✗ "Roster locked - regenerate to modify"
  ↓ Try to withdraw player → ✗ "Roster locked - regenerate to modify"
  ↓ Try to apply ratings → ✗ "Enter results first"
  
FIXTURE_FROZEN
  ↓ Try to regenerate → ✗ "Fixtures frozen - unlock to regenerate"
  ↓ Try to apply ratings → ✗ "Enter results first"
```

- [ ] Add `fixture_state` column to event table with enum
- [ ] Add `GET /events/{event_id}/fixtures/status` endpoint (returns current state & canRegenerate)
- [ ] Update `POST /events/{event_id}/players` to check fixture_state (block if not ROSTER_OPEN)
- [ ] Update `DELETE /events/{event_id}/players/{player_id}` to check fixture_state (block if not ROSTER_OPEN)
- [ ] Update `POST /events/{event_id}/generate-fixtures` to:
  - Check state is ROSTER_OPEN or FIXTURES_READY (block if FIXTURE_FROZEN)
  - Set fixture_state = 'FIXTURES_READY' on success
- [ ] Add `POST /events/{event_id}/fixtures/lock` endpoint (FIXTURES_READY → FIXTURE_FROZEN)
- [ ] Create `POST /events/{event_id}/apply-ratings` endpoint:
  - Check state is RESULTS_SUBMITTED
  - Update player ratings
  - Set state to RATINGS_APPLIED
- [ ] Update EventFixturesResponse to include fixture_state
- [ ] Update Admin.tsx:
  - Store selectedStrategy in state, update after generation
  - Show fixture_state status with buttons
  - Lock/unlock Generate, Register, Withdraw buttons based on state
- [ ] Add "Lock Fixtures" button (visible when FIXTURES_READY)
- [ ] Add "Apply Ratings" button (visible when RESULTS_SUBMITTED)
- [ ] Add confirmation dialogs for Regenerate and Lock actions
- [ ] Update all event-related responses to include fixture_state
