# JLRS Data Model v2

# Entities

---

## 1. Users

The authentication and authorization entity. All humans interacting with the system have a User record in the `users` table. A player may or may not have a linked User account (a player can be registered by a coach before they have the app).

| Field | Type | Required | Description |
|------|------|----------|------------|
| user_id | UUID | Yes | Unique identifier |
| name | String | Yes | Full name |
| email | String | Yes | Unique, used for login |
| password_hash | String | Nullable | Hashed password (null for OTP/Magic Link users) |
| last_login_at | Timestamp | Nullable | Last successful authentication |
| phone | String | Nullable | Optional contact |

| Field | Type | Required | Description |
|------|------|----------|------------|
| role | Enum | Yes | PLAYER, COACH, ADMIN, REFEREE, UMPIRE |
| academy_id | FK → Academy | Nullable | Required when role = COACH; null for ADMIN/REFEREE/UMPIRE and unlinked PLAYER |
| is_active | Boolean | Yes | False = suspended/deactivated |
| created_by | FK → Users | Nullable | Admin who created this account |
| deactivated_by | FK → Users | Nullable | Admin who deactivated this account |
| deactivated_at | Timestamp | Nullable | When account was deactivated |
| created_at | Timestamp | Yes | |
| updated_at | Timestamp | Yes | |

### Constraints

- email must be unique  
- phone must be unique (if provided)  
- academy_id must be non-null when role = COACH  
- PLAYER users may link to Player via Player.user_id  
- deactivated_by and deactivated_at must both be null or both non-null  

---

## 1b. UserIdentifierHistory

Tracks changes to primary identifiers (Email/Phone) for audit and security purposes.

| Field | Type | Required | Description |
|------|------|----------|------------|
| history_id | UUID | Yes | |
| user_id | FK → Users | Yes | |
| type | Enum | Yes | EMAIL, PHONE |
| old_value | String | Yes | |
| new_value | String | Yes | |
| changed_at | Timestamp | Yes | |
| changed_by | FK → Users | Yes | |
| reason | String | Nullable | |

---


## 2. Academy

A registered training academy that participates in the league.

| Field | Type | Required | Description |
|------|------|----------|------------|
| academy_id | UUID | Yes | Unique identifier |
| name | String | Yes | Academy name |
| location | String | Yes | Area / neighbourhood |
| city | String | Yes | City |
| state | String | Yes | State |
| status | Enum | Yes | ACTIVE, FROZEN, INACTIVE |
| frozen_since | Date | Nullable | When academy became inactive |
| min_tables | Integer | Yes | Minimum available tables |
| created_by | FK → Users | Yes | Admin who registered |
| updated_by | FK → Users | Yes | Last updater |
| created_at | Timestamp | Yes | |
| updated_at | Timestamp | Yes | |

### Status Lifecycle

- ACTIVE → FROZEN: auto when all players inactive ≥ 8 weeks  
- FROZEN → ACTIVE: auto when any player plays  
- ACTIVE/FROZEN → INACTIVE: manual admin action  

---

## 3. AcademyASIHistory

Append-only ASI recalculation log. Latest row = current ASI.

| Field | Type | Required | Description |
|------|------|----------|------------|
| history_id | UUID | Yes | |
| academy_id | FK → Academy | Yes | |
| asi_value | Decimal | Nullable | Mean rating (null if <5 players) |
| qualifying_player_count | Integer | Yes | |
| calculation_basis | Enum | Yes | COMPUTED, FROZEN, DEFAULTED |
| global_average_at_calculation | Decimal | Yes | Snapshot |
| calculated_at | Timestamp | Yes | |

### Rules

- Appended weekly  
- FROZEN → copy previous value  
- DEFAULTED → use global average  
- Qualifying players:  
  - rated_matches_completed ≥ 15  
  - last_match_date ≥ NOW() - 8 weeks  
  - status = ACTIVE  

---

## 3b. AcademyStatusHistory

Append-only status transition log.

| Field | Type | Required | Description |
|------|------|----------|------------|
| history_id | UUID | Yes | |
| academy_id | FK | Yes | |
| from_status | Enum | Nullable | |
| to_status | Enum | Yes | |
| reason | String | Nullable | Required for INACTIVE |
| triggered_by | Enum | Yes | SYSTEM, ADMIN |
| changed_by | FK → Users | Nullable | |
| changed_at | Timestamp | Yes | |

---

## 4. Player

A registered player.

### Stored Fields

| Field | Type | Required | Description |
|------|------|----------|------------|
| player_id | UUID | Yes | |
| user_id | FK → Users | Nullable | |
| name | String | Yes | |
| date_of_birth | Date | Yes | |
| seeding_level | Enum | Yes | UNSEEDED, DISTRICT, STATE, NATIONAL |
| seeding_reference | String | Nullable | |
| virtual_matches | Integer | Yes | |
| current_rating | Decimal | Yes | Cached |
| rated_matches_completed | Integer | Yes | Cached |
| last_match_date | Date | Nullable | Cached |
| primary_academy_id | FK → Academy | Yes | Cached |
| last_academy_change_date | Date | Nullable | |
| status | Enum | Yes | ACTIVE, INACTIVE, SUSPENDED |
| created_by | FK → Users | Yes | |
| updated_by | FK → Users | Yes | |
| created_at | Timestamp | Yes | |
| updated_at | Timestamp | Yes | |

### Notes

- Status history tracked in PlayerStatusHistory  
- Seeding corrections tracked in PlayerSeedingHistory  

---

## Computed Fields (Removed from storage)

| Field | Formula |
|------|--------|
| age_as_of_jan1 | Derived from date_of_birth |
| total_matches | rated_matches_completed + virtual_matches |
| is_provisional | seeding_level = UNSEEDED AND matches < 15 |
| tier | Derived from rating |
| confidence_ratio | Derived from matches + inactivity |
| weeks_inactive | (today - last_match_date) / 7 |

---

## 5. PlayerAcademyHistory

Tracks academy assignments.

| Field | Type | Required | Description |
|------|------|----------|------------|
| history_id | UUID | Yes | |
| player_id | FK | Yes | |
| academy_id | FK | Yes | |
| effective_from | Date | Yes | |
| effective_to | Date | Nullable | |
| change_reason | Enum | Yes | INITIAL_REGISTRATION, TRANSFER, CORRECTION |
| changed_by | FK → Users | Yes | |
| created_at | Timestamp | Yes | |

### Constraints

- Unique(player_id, effective_from)  
- Only one active academy (effective_to IS NULL)  

---

## 5b. PlayerStatusHistory

Append-only player status transitions.

| Field | Type | Required | Description |
|------|------|----------|------------|
| history_id | UUID | Yes | |
| player_id | FK | Yes | |
| from_status | Enum | Nullable | |
| to_status | Enum | Yes | |
| reason | String | Yes | |
| changed_by | FK → Users | Yes | |
| changed_at | Timestamp | Yes | |

---

## 5c. PlayerSeedingHistory

Tracks seeding corrections.

| Field | Type | Required | Description |
|------|------|----------|------------|
| history_id | UUID | Yes | |
| player_id | FK | Yes | |
| old_seeding_level | Enum | Yes | |
| new_seeding_level | Enum | Yes | |
| old_seeding_reference | String | Nullable | |
| new_seeding_reference | String | Nullable | |
| correction_reason | String | Yes | |
| corrected_by | FK → Users | Yes | |
| corrected_at | Timestamp | Yes | |
| rating_adjustment_applied | Boolean | Yes | |

---

## 6. Season

A defined competitive period.

| Field | Type | Required | Description |
|------|------|----------|------------|
| season_id | UUID | Yes | |
| name | String | Yes | |
| start_date | Date | Yes | |
| end_date | Date | Yes | |
| status | Enum | Yes | UPCOMING, ACTIVE, COMPLETED |
| created_by | FK → Users | Yes | |
| updated_by | FK → Users | Yes | |
| created_at | Timestamp | Yes | |
| updated_at | Timestamp | Yes | |

---

## 7. Event

A competition context.

### Scheduling Modes

- INTRA_ACADEMY  
- INTER_ACADEMY  

### Event Types

- LEAGUE  
- FRIENDLY  
- TOURNAMENT_EXTERNAL  
- TOURNAMENT_MANAGED  

### Core Fields

| Field | Type | Required | Description |
|------|------|----------|------------|
| event_id | UUID | Yes | |
| season_id | FK → Season | Nullable | |
| name | String | Yes | |
| event_type | Enum | Yes | |
| scheduling_mode | Enum | Yes | |
| default_match_format | Enum | Nullable | BEST_OF_3/5/7 |
| tournament_format | Enum | Nullable | |
| host_academy_id | FK → Academy | Nullable | |
| start_date | Date | Yes | |
| end_date | Date | Nullable | |
| status | Enum | Yes | SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED |

---

## Rating Update Triggers

| Scheduling Mode | Event Type | Trigger |
|----------------|-----------|--------|
| INTRA_ACADEMY | FRIENDLY | DAILY_EOD |
| INTER_ACADEMY | LEAGUE | EVENT_COMPLETION |
| INTER_ACADEMY | TOURNAMENT_EXTERNAL | EVENT_COMPLETION |
| INTER_ACADEMY | TOURNAMENT_MANAGED | EVENT_COMPLETION |

---

## Dispute Rules

### DAILY_EOD (Intra + Friendly)

- Only CONFIRMED / AUTO_CONFIRMED matches processed  
- DISPUTED matches excluded  

### EVENT_COMPLETION

- Event must be COMPLETED  
- No open disputes allowed  

---

## Notes

- ratings_update_trigger is derived, not stored  
- event_type immutable after IN_PROGRESS  

---

## 8. EventAcademy

Links events to academies.

| Field | Type | Required |
|------|------|----------|
| event_id | FK | Yes |
| academy_id | FK | Yes |
| added_by | FK → Users | Yes | |
| added_at | Timestamp | Yes |
| removed_by | FK → Users | Nullable | |
| removed_at | Timestamp | Nullable |

---

## 8b. EventReferee

Assigns referee to event.

| Field | Type | Required |
|------|------|----------|
| assignment_id | UUID | Yes |
| event_id | FK | Yes |
| user_id | FK → Users | Yes |
| assigned_by | FK → Users | Yes |
| assigned_at | Timestamp | Yes |

---

## 8c. EventUmpire

Assigns umpire per table.

| Field | Type | Required |
|------|------|----------|
| assignment_id | UUID | Yes |
| event_id | FK | Yes |
| user_id | FK → Users | Yes |
| table_number | Integer | Yes |
| assigned_by | FK → Users | Yes |
| assigned_at | Timestamp | Yes |

---

## 8d. EventPlayerRegistration

Tracks attendance.

| Field | Type | Required |
|------|------|----------|
| registration_id | UUID | Yes |
| event_id | FK | Yes |
| player_id | FK | Yes |
| registered_by | FK → Users | Yes |
| registered_at | Timestamp | Yes |
| status | Enum | Yes | REGISTERED, CHECKED_IN, WITHDRAWN, NO_SHOW |

---

## 8d. EventPlayerRegistration (continued)

| Field | Type | Required | Description |
|------|------|----------|------------|
| checked_in_by | FK → Users | Nullable | Who confirmed check-in |
| withdrawn_at | Timestamp | Nullable | When player withdrew |
| withdrawn_by | FK → Users | Nullable | Who recorded withdrawal |

### Constraints

- UNIQUE(event_id, player_id) — one registration per event  
- Only applicable to INTER_ACADEMY events  
- Pairing algorithm uses only players with status = CHECKED_IN  
- Player can only be matched if CHECKED_IN  

---

## 9. Session

A single daily training session within a league event.

| Field | Type | Required | Description |
|------|------|----------|------------|
| session_id | UUID | Yes | |
| event_id | FK → Event | Yes | |
| session_date | Date | Yes | |
| session_minutes | Integer | Yes | Duration |
| num_tables | Integer | Yes | |
| match_format | Enum | Yes | BEST_OF_3 / BEST_OF_5 |
| bootstrap_phase | Enum | Yes | DISCOVERY, TRANSITION, STANDARD |
| rating_spread | Decimal | Yes | max_rating - min_rating |
| matches_per_player | Integer | Yes | |
| present_player_count | Integer | Yes | |
| status | Enum | Yes | SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED |
| generated_at | Timestamp | Nullable | |
| generated_by | FK → Users | Nullable | |
| created_by | FK → Users | Yes | |
| updated_by | FK → Users | Yes | |
| created_at | Timestamp | Yes | |
| updated_at | Timestamp | Yes | |

### Constraints

- UNIQUE(event_id, session_date)

---

## 10. FixtureSlot

Represents a scheduled matchup inside a session.

| Field | Type | Required | Description |
|------|------|----------|------------|
| slot_id | UUID | Yes | |
| session_id | FK → Session | Yes | |
| round_number | Integer | Yes | |
| sub_round | Enum | Nullable | A / B |
| table_number | Integer | Yes | |
| match_category | Enum | Yes | COMPETITIVE, STRETCH, ANCHOR |
| player_a_id | FK → Player | Yes | |
| player_b_id | FK → Player | Yes | |
| expected_rating_gap | Decimal | Yes | |
| status | Enum | Yes | SCHEDULED, PLAYED, UNPLAYED, BYE |
| match_id | FK → Match | Nullable | |
| updated_by | FK → Users | Nullable | |
| created_at | Timestamp | Yes | |
| updated_at | Timestamp | Yes | |

### Constraints

- UNIQUE(session_id, round_number, sub_round, table_number)  
- match_id nullable (e.g., BYE)  
- One slot per player per round  

---

## 11. Match

A single rated match between two players.

| Field | Type | Required | Description |
|------|------|----------|------------|
| match_id | UUID | Yes | |
| event_id | FK → Event | Yes | |
| session_id | FK → Session | Nullable | |
| player_a_id | FK → Player | Yes | |
| player_b_id | FK → Player | Yes | |
| player_a_academy_id | FK → Academy | Yes | Snapshot |
| player_b_academy_id | FK → Academy | Yes | Snapshot |
| match_format | Enum | Yes | BEST_OF_3 / 5 / 7 |
| sets_won_a | Integer | Yes | |
| sets_won_b | Integer | Yes | |
| sets_won_a_actual | Integer | Nullable | |
| sets_won_b_actual | Integer | Nullable | |
| is_retirement | Boolean | Yes | |
| winner_id | FK → Player | Yes | |
| rating_eligible | Boolean | Yes | |
| not_eligible_reason | Enum | Nullable | |
| ratings_applied_at | Timestamp | Nullable | |
| diminishing_signal_applied | Boolean | Yes | |
| match_category | Enum | Nullable | |
| match_date | Date | Yes | |
| match_timestamp | Timestamp | Yes | |
| umpire_id | FK → Users | Nullable | |
| submitted_by | FK → Users | Yes | |
| confirmed_by | FK → Users | Nullable | |
| confirmation_status | Enum | Yes | |
| confirmation_deadline | Timestamp | Yes | |
| confirmed_at | Timestamp | Nullable | |
| voided_at | Timestamp | Nullable | |
| voided_by | FK → Users | Nullable | |
| void_reason | String | Nullable | |
| created_at | Timestamp | Yes | |
| updated_at | Timestamp | Yes | |

---

## Confirmation Flow

```
SUBMITTED → PENDING

IF dispute raised:
    → DISPUTED (rating deferred)

IF confirmed:
    → CONFIRMED
    → rating applied immediately

IF deadline passes:
    → AUTO_CONFIRMED
    → rating applied
```

---

## Rating Update Conditions

All must be true:

```
rating_eligible = true
AND confirmation_status IN (CONFIRMED, AUTO_CONFIRMED)
AND ratings_applied_at IS NULL
AND (
    DAILY_EOD (INTRA_ACADEMY + FRIENDLY)
    OR
    EVENT_COMPLETION (INTER_ACADEMY)
)
```

---

## Effective Event Type (Computed)

```
effective_event_type =
    IF diminishing_signal_applied = true
    THEN FRIENDLY
    ELSE event_type
```

---

## Walkover Detection

```
sets_won_a = 0 AND sets_won_b = 0
AND is_retirement = false
→ WALKOVER
```

---

## 12. RatingHistory

Append-only rating audit log.

| Field | Type | Required |
|------|------|----------|
| history_id | UUID | Yes |
| player_id | FK → Player | Yes |
| match_id | FK → Match | Yes |
| rating_before | Decimal | Yes |
| rating_after | Decimal | Yes |
| delta | Decimal | Yes |
| delta_breakdown | JSONB | Yes |
| tier_before | Enum | Yes |
| tier_after | Enum | Yes |
| cr_before | Decimal | Yes |
| cr_after | Decimal | Yes |
| k_base | Decimal | Yes |
| k_eff | Decimal | Yes |
| k_shared | Decimal | Yes |
| expected_score | Decimal | Yes |
| actual_score | Decimal | Yes |
| age_bonus | Decimal | Yes |
| is_rollback | Boolean | Yes |
| rollback_of_history_id | FK | Nullable |
| created_at | Timestamp | Yes |

---

## delta_breakdown JSON (schema)

```json
{
  "academy_normalization": {
    "applied": true,
    "asi_self": 1200,
    "asi_opponent": 1150,
    "global_average": 1100,
    "r_adj_self": 1250,
    "r_adj_opponent": 1200
  },
  "expected_score": 0.57,
  "actual_score": 1.0,
  "k_calculation": {
    "k_base": 50,
    "w_match": 1.2,
    "w_academy": 1.2,
    "cr_self": 0.49,
    "k_eff_self": 60,
    "k_eff_opponent": 52.3,
    "k_shared": 56.15
  },
  "base_elo_delta": 24.1,
  "age_bonus": {
    "applied": true,
    "bonus_amount": 4
  },
  "total_delta": 28.1
}
```

---

## 13. Dispute

Tracks contested matches.

| Field | Type | Required |
|------|------|----------|
| dispute_id | UUID | Yes |
| match_id | FK → Match | Yes |
| raised_by | FK → Users | Yes |
| reason | String | Yes |
| status | Enum | Yes | OPEN, UNDER_REVIEW, RESOLVED, EXPIRED |
| resolution | Enum | Nullable | CONFIRMED_ORIGINAL, CORRECTED, VOIDED |
| corrected_sets_won_a | Integer | Nullable |
| corrected_sets_won_b | Integer | Nullable |
| resolved_by | FK → Users | Nullable |
| resolution_notes | String | Nullable |
| reviewed_by | FK → Users | Nullable |
| reviewed_at | Timestamp | Nullable |
| resolution_deadline | Timestamp | Yes |
| created_at | Timestamp | Yes |
| resolved_at | Timestamp | Nullable |

---

## Resolution Authority

- INTER_ACADEMY events → referee resolves  
- Others → admin resolves  

---

## 13b. DisputeStatusHistory

Append-only dispute lifecycle log.

| Field | Type | Required |
|------|------|----------|
| history_id | UUID | Yes |
| dispute_id | FK → Dispute | Yes |
| from_status | Enum | Nullable |
| to_status | Enum | Yes |
| changed_by | FK → Users | Nullable | |
| triggered_by | Enum | Yes | ADMIN, REFEREE, SYSTEM |
| notes | String | Nullable |
| changed_at | Timestamp | Yes |

---

## 14. SystemConfiguration

Runtime config store.

| Field | Type | Required |
|------|------|----------|
| key | String | Yes |
| value | String | Yes |
| description | String | Yes |
| updated_by | FK → Users | Yes | |
| updated_at | Timestamp | Yes |

---

## Initial Parameters

| Key | Default |
|-----|--------|
| starting_rating_unseeded | 1000 |
| starting_rating_district | 1200 |
| starting_rating_state | 1400 |
| starting_rating_national | 1500 |
| provisional_match_threshold | 15 |
| k_base_new | 50 |
| k_base_mid | 32 |
| k_base_veteran | 20 |
| age_bonus_max | 10 |
| w_match_league | 1.0 |
| w_match_tournament | 1.2 |
| w_match_friendly | 0.5 |

---

## 15. SystemConfigurationHistory

Append-only config changes.

| Field | Type | Required |
|------|------|----------|
| history_id | UUID | Yes |
| key | String | Yes |
| old_value | String | Yes |
| new_value | String | Yes |
| changed_by | FK → Users | Yes | |
| changed_at | Timestamp | Yes |
| effective_for_matches_after | Timestamp | Yes |

---

## Enumerations

### UserRole
PLAYER, COACH, ADMIN, REFEREE, UMPIRE

### MatchFormat
BEST_OF_3, BEST_OF_5, BEST_OF_7

### EventType
LEAGUE, FRIENDLY, TOURNAMENT_EXTERNAL, TOURNAMENT_MANAGED

### ConfirmationStatus
PENDING, CONFIRMED, DISPUTED, VOIDED, AUTO_CONFIRMED

### Tier
BEGINNER, INTERMEDIATE, ADVANCED, ELITE, NATIONAL_TRACK

---

# Database Constraints and Indexes

---

## Check Constraints

| Table | Constraint | Note |
|------|-----------|------|
| Event | CHECK(NOT (scheduling_mode = 'INTRA_ACADEMY' AND event_type = 'LEAGUE')) | All intra-academy matches are FRIENDLY; LEAGUE weight must not be applied |
| Event | CHECK(NOT (scheduling_mode = 'INTRA_ACADEMY' AND event_type = 'TOURNAMENT_EXTERNAL')) | External tournaments are cross-academy |
| Event | CHECK(NOT (scheduling_mode = 'INTRA_ACADEMY' AND event_type = 'TOURNAMENT_MANAGED')) | JLRS-managed tournaments require multiple academies |

---

| Table | Constraint | Note |
|------|-----------|------|
| Event | CHECK(NOT (scheduling_mode = 'INTER_ACADEMY' AND event_type = 'FRIENDLY')) | Cross-academy friendlies invalid |
| Match | CHECK(player_a_id < player_b_id) | Enforces canonical ordering for deduplication |
| Match | CHECK(NOT (rating_eligible = false AND not_eligible_reason IS NULL)) | Reason required when not eligible |
| Match | CHECK(NOT (ratings_applied_at IS NOT NULL AND rating_eligible = false)) | Cannot apply ratings to ineligible match |

---

## Unique Constraints

| Table | Constraint | Note |
|------|-----------|------|
| Users | UNIQUE(email) | |
| ClusterMembership | UNIQUE(academy_id) WHERE left_at IS NULL | One active cluster per academy |
| ClusterMembership | UNIQUE(cluster_id, host_rotation_order) | |
| PlayerAcademyHistory | UNIQUE(player_id, effective_from) | |
| Session | UNIQUE(event_id, session_date) | One session per event per day |
| FixtureSlot | UNIQUE(session_id, round_number, sub_round, table_number) | |
| Match | UNIQUE(player_a_id, player_b_id, event_id, match_date) | DB-level deduplication |
| EventReferee | UNIQUE(event_id, user_id) WHERE revoked_at IS NULL | One active referee assignment |
| EventUmpire | UNIQUE(event_id, table_number) WHERE revoked_at IS NULL | One umpire per table |
| EventUmpire | UNIQUE(event_id, user_id) WHERE revoked_at IS NULL | One table per umpire |
| EventPlayerRegistration | UNIQUE(event_id, player_id) | |
| Dispute | UNIQUE(match_id) WHERE status IN ('OPEN', 'UNDER_REVIEW') | One active dispute per match |

---

## Performance Indexes

| Table | Index / Query Pattern | Purpose |
|------|---------------------|---------|
| Player | (status, current_rating DESC) | Global leaderboard |
| Player | (primary_academy_id, status, current_rating DESC) | Academy leaderboard |
| Player | (date_of_birth, status, current_rating DESC) | Age-group leaderboard |
| Player | (last_match_date) WHERE status = 'ACTIVE' | Inactivity decay scheduler |
| PlayerAcademyHistory | (player_id) WHERE effective_to IS NULL | Current academy lookup |
| PlayerAcademyHistory | (player_id, effective_from, effective_to) | Point-in-time lookup |
| Match | (player_a_id, player_b_id, match_date DESC) | Diminishing signal detection |
| Match | (player_b_id, confirmation_status) WHERE confirmation_status = 'PENDING' | Pending confirmations |
| Match | (event_id, match_date) | Event result view |
| Match | (match_date, confirmation_status) WHERE confirmation_status = 'PENDING' | EOD auto-confirmation |
| Match | (match_date, rating_eligible, ratings_applied_at) | Daily rating batch |
| Match | (event_id, rating_eligible, ratings_applied_at) | Event completion batch |
| RatingHistory | (player_id, created_at DESC) | Player rating history |
| RatingHistory | (match_id) | Match breakdown lookup |
| AcademyASIHistory | (academy_id, calculated_at DESC) | Current ASI lookup |
| Dispute | (status) WHERE status IN ('OPEN', 'UNDER_REVIEW') | Admin queue |
| Dispute | (resolution_deadline) WHERE status IN ('OPEN', 'UNDER_REVIEW') | Auto-expiry |
| DisputeStatusHistory | (dispute_id, changed_at DESC) | Timeline |
| PlayerStatusHistory | (player_id, changed_at DESC) | Timeline |
| AcademyStatusHistory | (academy_id, changed_at DESC) | Timeline |
| PlayerSeedingHistory | (player_id, corrected_at DESC) | Audit |
| EventAcademy | (event_id) WHERE removed_at IS NULL | Active academies |
| EventPlayerRegistration | (event_id, status) | Checked-in players |
| EventPlayerRegistration | (player_id, event_id) | Registration lookup |
| EventReferee | (event_id) WHERE revoked_at IS NULL | Active referee |
| EventUmpire | (event_id) WHERE revoked_at IS NULL | Active umpires |
| EventUmpire | (event_id, table_number) WHERE revoked_at IS NULL | Table lookup |
| Match | (confirmation_deadline) WHERE confirmation_status = 'PENDING' | Dispute expiry |

---

# Denormalization Register

These fields intentionally violate 3NF for performance.

| Field | Table | Derived From | Write Rule | Risk |
|------|------|--------------|------------|------|
| current_rating | Player | Latest RatingHistory.rating_after | Update atomically with RatingHistory insert | Leaderboard inconsistency |
| rated_matches_completed | Player | COUNT(RatingHistory) | Increment atomically | Threshold errors |
| last_match_date | Player | MAX(Match.match_date) | Update on rating application | Inactivity errors |
| primary_academy_id | Player | PlayerAcademyHistory | Update on change | Wrong normalization |
| global_average_rating | SystemConfiguration | Weekly ASI computation | Updated with ASI batch | Stale baseline |

---

# Computed Fields Reference

These values are **never stored**.

| Field | Formula | Used For |
|------|--------|---------|
| age_as_of_jan1 | CURRENT_YEAR - YEAR(date_of_birth) (adjusted for Jan 1 cutoff) | Age groups |
| total_matches | rated_matches_completed + virtual_matches | CR calculation |
| is_provisional | seeding_level = UNSEEDED AND matches < threshold | K override |
| tier | Lookup(current_rating) | UI / pairing |
| confidence_ratio | \( 1 - e^{-(total\_matches / cr\_denominator)} \) | K_eff |
| weeks_inactive | (NOW - last_match_date) / 7 | CR decay |
| effective_event_type | IF diminishing_signal_applied THEN FRIENDLY ELSE event_type | Match weight |
| current_asi | Latest AcademyASIHistory row | Normalization |
| is_cross_academy | COUNT(EventAcademy) > 1 | Academy multiplier |

---
