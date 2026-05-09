
# JLRS API Contract v2

This document defines the complete REST API for the JLRS system, updated to align with the v2 data model. All request and response bodies are JSON. Timestamps are ISO 8601 UTC. UUIDs are lowercase hyphenated strings.

---

## What Changed from v1

| v1 Gap | v2 Resolution |
|--------|-------------|
| No authentication or User endpoints | `POST /auth/login`, `POST /users` added |
| No player computed stats endpoint | `GET /players/{id}/computed-stats` added |
| No academy transfer history endpoint | `GET /players/{id}/academy-history` added |
| No session or fixture endpoints | Full `/sessions` resource with fixture generation added |
| No ASI history endpoint | `GET /academies/{id}/asi-history` added |
| No config history endpoint | `GET /config/history` added |
| Event participating academies managed inline | `POST /events/{id}/academies` manages EventAcademy |
| Dispute resolution missing corrected fields | `corrected_sets_won_a/b` in resolve request body |
| Rating history breakdown was partial | Full `delta_breakdown` object in every history entry |
| `match_type` referred to event’s type | Renamed to `event_type`; scheduling_mode field added |
| Authentication limited to passwords | Support for passwordless/OTP added via nullable `password_hash` |
| No identifier audit trail | `UserIdentifierHistory` added to track email/phone changes |


Only 2 match types (`LEAGUE`, `FRIENDLY`) → 4 event types: `LEAGUE`, `FRIENDLY`, `TOURNAMENT_EXTERNAL`, `TOURNAMENT_MANAGED`

- `INTRA_ACADEMY` + `LEAGUE` was valid → Blocked — all intra-academy play is `FRIENDLY`
- `INTRA_ACADEMY` + `TOURNAMENT_MANAGED` was valid → Blocked — JLRS-managed tournaments are `INTER_ACADEMY` only

---

## Rating Processing Changes

- Ratings applied synchronously on confirmation → Ratings applied async:
  - DAILY_EOD (`INTRA_ACADEMY + FRIENDLY`)
  - EVENT_COMPLETION (all `INTER_ACADEMY`)

- Confirmation window was 48 hours → Deadline = end of match day (23:59:59 local time)

- `COMPLETED` could proceed with open disputes → Blocked if open disputes (409 returned)

- No referee/umpire roles → Added

- `is_rated` boolean → Split into:
  - `rating_eligible`
  - `ratings_applied_at`

---

## Authentication

All endpoints (except `/auth/login`) require a Bearer token.

```
Authorization: Bearer <token>
```

---

## Roles

| Role | Scope |
|------|------|
| PLAYER | Own profile, own match submissions, own rating history |
| COACH | All players in their academy; match submission; event/session creation |
| ADMIN | All data; dispute resolution; void matches; system configuration |
| REFEREE | Assigned events only; submit/confirm matches; resolve disputes |
| UMPIRE | Assigned table only; submit match results |

---

## Login

### POST /api/v1/auth/login

**Request**
```json
{
  "email": "coach@academyx.com", 
  "password": "...",
  "otp_code": "123456"
}
```

**Response (200)**
```json
{
  "token": "eyJ...",
  "user_id": "uuid-user-1",
  "role": "COACH",
  "academy_id": "uuid-academy-x",
  "expires_at": "2026-04-19T10:00:00Z"
}
```

---

# 1. Users

## Register User

### POST /api/v1/users

Roles:
- ADMIN (for COACH and ADMIN accounts)
- Any authenticated user can register PLAYER

**Request**
```json
{
  "name": "Vikram Nair",
  "email": "vikram@academyx.com",
  "phone": "+919876543210",
  "role": "COACH",
  "academy_id": "uuid-academy-x"
}
```

**Response (201)**
```json
{
  "user_id": "uuid-user-1",
  "name": "Vikram Nair",
  "email": "vikram@academyx.com",
  "role": "COACH",
  "academy_id": "uuid-academy-x",
  "is_active": true,
  "created_at": "2026-04-01T09:00:00Z"
}
```

---

## Validation

- `email` must be unique  
- `academy_id` required when role = COACH  
- role = ADMIN requires ADMIN caller  
- role = REFEREE or UMPIRE requires ADMIN caller  

---

## Get User

### GET /api/v1/users/{user_id}

Roles: ADMIN or self

---

# 2. Players

## Register Player

### POST /api/v1/players

Roles: COACH (for players in their academy), ADMIN

### Request — unseeded
```json
{
  "name": "Arjun Kumar",
  "date_of_birth": "2014-05-20",
  "primary_academy_id": "uuid-academy-x",
  "seeding_level": "UNSEEDED",
  "virtual_matches": 0
}
```

### Request — seeded
```json
{
  "name": "Priya Sharma",
  "date_of_birth": "2012-08-14",
  "primary_academy_id": "uuid-academy-y",
  "seeding_level": "STATE",
  "seeding_reference": "MSTTA-2025-U13-Rank-5"
}
```

---

### Response (201)
```json
{
  "player_id": "uuid-player-1",
  "name": "Arjun Kumar",
  "current_rating": 1000,
  "virtual_matches": 0,
  "rated_matches_completed": 0,
  "seeding_level": "UNSEEDED",
  "primary_academy": {
    "academy_id": "uuid-academy-x",
    "name": "TT Academy X"
  },
  "status": "ACTIVE",
  "created_at": "2026-04-01T09:00:00Z"
}
```

---

## Validation

- `date_of_birth` must make player age between 6–18 years old
- `primary_academy_id` must reference an ACTIVE academy
- `seeding_reference` required when seeding_level ≠ UNSEEDED`

---

---

## Get Player Profile

### GET /api/v1/players/{player_id}

Returns stored fields only. For computated stats (tier, CR, provisional status), use `/players/{id}/computed-stats`.


---

### Response (200)
```json
{
  "player_id": "uuid-player-1",
  "name": "Arjun Kumar",
  "current_rating": 1078,
  "rated_matches_completed": 8,
  "virtual_matches": 0,
  "seeding_level": "UNSEEDED",
  "primary_academy": {
    "academy_id": "uuid-academy-x",
    "name": "TT Academy X"
  },
  "last_match_date": "2026-03-25",
  "status": "ACTIVE",
  "created_at": "2026-01-01T08:00:00Z"
}
```

---

## Visibility

- `current_rating` visible to all authenticated users  . Ratings are public - transparency is consistent with leaderboards and encourages engagement
- All other fields visible to all authenticated users with access to this player

---

## Get Player Computed Stats

### GET /api/v1/players/{player_id}/computed-stats

**Response (200)**
```json
{
  "player_id": "uuid-player-1",
  "as_of": "2026-04-12T14:30:00Z",
  "age_as_of_jan1": 11,
  "age_group": "U13",
  "total_matches": 8,
  "is_provisional": true,
  "provisional_matches_remaining": 7,
  "tier": "INTERMEDIATE",
  "confidence_ratio": 0.23,
  "weeks_inactive": 2,
  "inactivity_decay_active": false
}
```

---

**Notes:**

- `as_of` is the server timestamp at which these values were computed  
- `age_group` is derived from `age_as_of_jan1`: U10 (≤10), U13 (11–13), U15 (14–15), U17 (16–17)  
- `inactivity_decay_active`: true when `weeks_inactive > inactivity_threshold_weeks` config value  

---

## Get Player Rating History

### GET /api/v1/players/{player_id}/rating-history?limit=20&offset=0

---

**Visibility:**

- All authenticated users can call this endpoint and see match results, rating before/after, and delta  
- `delta_breakdown` (full calculation detail including CR, K-factors, age bonus) is returned only when the caller is:
  - The player themselves  
  - A coach of the player’s current academy  
  - An admin  
- For all other callers, `delta_breakdown` is omitted  

---

**Visibility:**

- **All authenticated users** can call this endpoint and see match results, rating before/after, and delta  
- `delta_breakdown` (full calculation detail including CR, K-factors, age bonus) is returned only when the caller is:  
  - The player themselves  
  - A coach of the player's current academy  
  - An admin  
- For all other callers, `delta_breakdown` is omitted from each history entry  

---

**Response (200) — player / coach / admin (full breakdown):**
```json
{
  "player_id": "uuid-player-1",
  "history": [
    {
      "history_id": "uuid-hist-1",
      "match_id": "uuid-match-1",
      "match_date": "2026-03-25",
      "opponent": {
        "player_id": "uuid-player-2",
        "name": "Rahul Mehta",
        "tier": "INTERMEDIATE"
      },
      "result": "WIN",
      "set_score": "3-1",
      "rating_before": 1053,
      "rating_after": 1078,
      "delta": 25,
      "delta_breakdown": {
        "academy_normalization": { "applied": false },
        "expected_score": 0.45,
        "actual_score": 0.90,
        "k_calculation": {
          "k_base": 50,
          "w_match": 1.0,
          "w_academy": 0.8,
          "cr_self": 0.15,
          "two_minus_cr": 1.85,
          "k_eff_self": 60.0,
          "k_eff_opponent": 48.0,
          "k_shared": 54.0,
          "k_cap_applied": true
        },
        "base_elo_delta": 24.3,
        "age_bonus": { "applied": false, "bonus_amount": 0 },
        "total_delta": 24.3,
        "effective_event_type": "LEAGUE",
        "diminishing_signal_applied": false,
        "provisional_k_override": true
      },
      "tier_before": "INTERMEDIATE",
      "tier_after": "INTERMEDIATE",
      "is_rollback": false
    }
  ],
  "pagination": { "total": 8, "limit": 20, "offset": 0 }
}
```

---

**Response (200) — all other authenticated users (breakdown omitted):**
```json
{
  "player_id": "uuid-player-1",
  "history": [
    {
      "history_id": "uuid-hist-1",
      "match_id": "uuid-match-1",
      "match_date": "2026-03-25",
      "opponent": {
        "player_id": "uuid-player-2",
        "name": "Rahul Mehta",
        "tier": "INTERMEDIATE"
      },
      "result": "WIN",
      "set_score": "3-1",
      "rating_before": 1053,
      "rating_after": 1078,
      "delta": 25,
      "tier_before": "INTERMEDIATE",
      "tier_after": "INTERMEDIATE",
      "is_rollback": false
    }
  ],
  "pagination": { "total": 8, "limit": 20, "offset": 0 }
}
```

---

### Get Player Academy History

GET /api/v1/players/{player_id}/academy-history

Roles: the player, their academy’s coaches, ADMIN.


**Response (200):**
```json
{
  "player_id": "uuid-player-1",
  "history": [
    {
      "history_id": "uuid-pah-1",
      "academy": {
        "academy_id": "uuid-academy-x",
        "name": "TT Academy X"
      },
      "effective_from": "2026-01-10",
      "effective_to": null,
      "change_reason": "INITIAL_REGISTRATION",
      "changed_by": "uuid-user-coach-1"
    }
  ]
}
```

---

### Transfer Player Academy

PATCH /api/v1/players/{player_id}/academy

Roles: ADMIN, or COACH of the player's current academy.

**Request:**
```json
{
  "new_academy_id": "uuid-academy-y",
  "effective_date": "2026-05-01"
}
```

---

**Response (200):**
```json
{
  "player_id": "uuid-player-1",
  "new_primary_academy_id": "uuid-academy-y",
  "effective_date": "2026-05-01",
  "next_change_allowed_after": "2026-08-01"
}
```

---

**Validation:**

- `effective_date` must be the 1st of a future calendar month  
- `last_academy_change_date` must be more than one quarter ago (or null)  

---

## 3. Academies

### Register Academy

POST /api/v1/academies

Roles: ADMIN.

---

**Request:**
```json
{
  "name": "TT Academy X",
  "location": "Andheri West",
  "city": "Mumbai",
  "state": "Maharashtra",
  "min_tables": 4
}
```

---

**Response (201):**
```json
{
  "academy_id": "uuid-academy-x",
  "name": "TT Academy X",
  "city": "Mumbai",
  "state": "Maharashtra",
  "status": "ACTIVE",
  "created_at": "2026-01-01T00:00:00Z"
}
```

---

### Get Academy

GET /api/v1/academies/{academy_id}

---

**Response (200):**
```json
{
  "academy_id": "uuid-academy-x",
  "name": "TT Academy X",
  "location": "Andheri West",
  "city": "Mumbai",
  "state": "Maharashtra",
  "status": "ACTIVE",
  "current_asi": 1180,
  "asi_player_count": 12,
  "asi_last_calculated": "2026-04-07T00:00:00Z",
  "active_player_count": 18
}
```

---

**Note:** `current_asi` is fetched from the latest `AcademyASIHistory` row, not a stored field on Academy.

---

### Get Academy Leaderboard

GET /api/v1/academies/{academy_id}/leaderboard?tier=ADVANCED&limit=20&offset=0

---

**Response (200):**
```json
{
  "academy_id": "uuid-academy-x",
  "tier_filter": "ADVANCED",
  "players": [
    {
      "rank": 1,
      "player_id": "uuid-player-5",
      "name": "Sneha Patel",
      "current_rating": 1285,
      "tier": "ADVANCED",
      "rated_matches_completed": 45,
      "is_provisional": false
    }
  ],
  "pagination": { "total": 6, "limit": 20, "offset": 0 }
}
```

---

### Get Academy ASI History

GET /api/v1/academies/{academy_id}/asi-history?limit=12

Roles: ADMIN, COACH of that academy.

---

**Response (200):**
```json
{
  "academy_id": "uuid-academy-x",
  "history": [
    {
      "history_id": "uuid-asi-1",
      "asi_value": 1180,
      "qualifying_player_count": 12,
      "calculation_basis": "COMPUTED",
      "global_average_at_calculation": 1095,
      "calculated_at": "2026-04-07T00:00:00Z"
    },
    {
      "history_id": "uuid-asi-2",
      "asi_value": 1165,
      "qualifying_player_count": 10,
      "calculation_basis": "COMPUTED",
      "global_average_at_calculation": 1090,
      "calculated_at": "2026-03-31T00:00:00Z"
    }
  ]
}
],
"pagination": { "total": 24, "limit": 12, "offset": 0 }
}
...
---

## 4. Seasons

### Create Season

POST /api/v1/seasons

Roles: ADMIN.

**Request:**
```json
{
  "name": "2026 Summer League",
  "start_date": "2026-06-01",
  "end_date": "2026-09-30"
}
```

---

**Response (201):**
```json
{
  "season_id": "uuid-season-1",
  "name": "2026 Summer League",
  "start_date": "2026-06-01",
  "end_date": "2026-09-30",
  "status": "UPCOMING",
  "created_at": "2026-04-12T00:00:00Z"
}
```

...

---

### List Seasons

GET /api/v1/seasons?status=ACTIVE

---

### Update Season Status

PATCH /api/v1/seasons/{season_id}/status

Roles: ADMIN.

**Request:**
```json
{
  "status": "ACTIVE"
}
```

Valid transitions: UPCOMING → ACTIVE, ACTIVE → COMPLETED

---

## 5. Events

### Create Event

POST /api/v1/events

Roles: COACH, ADMIN.

**Request:**
```json
{
  "season_id": "uuid-season-1",
  "name": "April Cross-Academy League — Mumbai North",
  "scheduling_mode": "INTER_ACADEMY",
  "event_type": "LEAGUE",
  "default_match_format": "BEST_OF_3",
  "host_academy_id": "uuid-academy-x",
  "participating_academy_ids": ["uuid-academy-x", "uuid-academy-y"],
  "start_date": "2026-04-14",
  "end_date": "2026-04-14"
}
```

---

**Response (201):**
```json
{
  "event_id": "uuid-event-1",
  "name": "April Cross-Academy League — Mumbai North",
  "scheduling_mode": "INTER_ACADEMY",
  "event_type": "LEAGUE",
  "default_match_format": "BEST_OF_3",
  "is_cross_academy": true,
  "season": {"season_id": "uuid-season-1", "name": "2026 Summer League"},
  "participating_academies": [
    {"academy_id": "uuid-academy-x", "name": "TT Academy X"},
    {"academy_id": "uuid-academy-y", "name": "TT Academy Y"}
  ],
  "start_date": "2026-04-14",
  "end_date": "2026-04-14",
  "status": "SCHEDULED",
  "created_at": "2026-04-12T10:00:00Z"
}
```

---

**Validation:**

- scheduling_mode must be INTRA_ACADEMY or INTER_ACADEMY  
- event_type must be LEAGUE, FRIENDLY, TOURNAMENT_EXTERNAL, or TOURNAMENT_MANAGED  
- The scheduling_mode + event_type combination must be valid:
  - INTRA_ACADEMY + LEAGUE → **rejected** (422): all within-academy matches must use FRIENDLY  
  - INTRA_ACADEMY + TOURNAMENT_EXTERNAL → **rejected** (422): external tournaments are cross-academy  
  - INTRA_ACADEMY + TOURNAMENT_MANAGED → **rejected** (422): JLRS-managed tournaments require multiple academies  
  - INTER_ACADEMY + FRIENDLY → **rejected** (422): use intra-academy friendly at each academy instead  

- end_date is required for all INTER_ACADEMY events and all tournament types; optional for INTRA_ACADEMY + FRIENDLY  
- start_date must be today or in the future  
- season_id is optional (null for off-season events)  

---

### Add Academy to Event

```

POST /api/v1/events/{event_id}/academies

```
Roles: `ADMIN`, or `COACH` of the academy being added.

**Request:**
```json
{
  "academy_id": "uuid-academy-y"
}
```

---

**Response (201):**
```json
{
  "event_id": "uuid-event-1",
  "academy_id": "uuid-academy-y",
  "is_cross_academy": true
}
```

---

### Get Event

GET /api/v1/events/{event_id}

---

**Response (200):**
```json
{
  "event_id": "uuid-event-1",
  "name": "April Cross-Academy League — Mumbai North",
  "scheduling_mode": "INTER_ACADEMY",
  "event_type": "LEAGUE",
  "default_match_format": "BEST_OF_3",
  "is_cross_academy": true,
  "season": {"season_id": "uuid-season-1", "name": "2026 Summer League"},
  "participating_academies": [
    {"academy_id": "uuid-academy-x", "name": "TT Academy X"},
    {"academy_id": "uuid-academy-y", "name": "TT Academy Y"}
  ],
  "start_date": "2026-04-14",
  "end_date": "2026-04-14",
  "status": "IN_PROGRESS",
  "session_count": 2,
  "match_count": 36
}
```

---

### Update Event Status

PATCH /api/v1/events/{event_id}/status

Roles: ADMIN, COACH of the host academy.

**Request:**
```json
{
  "status": "IN_PROGRESS"
}
```

---

**Valid transitions:**

| From | To | Rule |
|------|----|------|
| SCHEDULED | IN_PROGRESS | Allowed freely; event_type and scheduling_mode become immutable from this point |
| IN_PROGRESS | COMPLETED | **Blocked if any dispute for the event is OPEN or UNDER_REVIEW** (see below) |
| SCHEDULED or IN_PROGRESS | CANCELLED | Allowed; voids all unrated matches in the event |
| COMPLETED | any | Not allowed |

---

**Dispute pre-condition check (→ COMPLETED only):**

Before accepting the transition the service checks for unresolved disputes:

```sql
SELECT dispute_id FROM Dispute
WHERE match_id IN (SELECT match_id FROM Match WHERE event_id = :event_id)
AND status IN ('OPEN', 'UNDER_REVIEW')
```

If any disputes are found, the request is rejected with 409 Conflict. The admin must resolve or allow all open disputes to expire before retrying.

---

**Responses:**

200 OK — transition accepted:
```json
{
  "event_id": "uuid-event-1",
  "status": "COMPLETED",
  "updated_at": "2026-04-13T20:00:00Z"
}
```

409 Conflict — unresolved disputes block → COMPLETED:
```json
{
  "error": "EVENT_HAS_OPEN_DISPUTES",
  "message": "Event cannot be completed while disputes are open. Resolve all disputes first.",
  "open_disputes": [
    {"dispute_id": "uuid-dispute-1", "match_id": "uuid-match-1", "status": "OPEN"},
    {"dispute_id": "uuid-dispute-2", "match_id": "uuid-match-2", "status": "UNDER_REVIEW"}
  ]
}
```

422 Unprocessable Entity — invalid transition (e.g., COMPLETED → IN_PROGRESS):
```json
{
  "error": "INVALID_STATUS_TRANSITION",
  "message": "Cannot transition from COMPLETED to IN_PROGRESS."
}
```

---

### Assign Referee to Event

POST /api/v1/events/{event_id}/referees

Roles: ADMIN.

Only applicable to INTER_ACADEMY + LEAGUE and INTER_ACADEMY + TOURNAMENT_MANAGED events.

**Request:**
```json
{
  "user_id": "uuid-user-referee-1"
}
```

---

**Response (201):**
```json
{
  "assignment_id": "uuid-ref-assignment-1",
  "event_id": "uuid-event-1",
  "user_id": "uuid-user-referee-1",
  "assigned_at": "2026-04-12T10:00:00Z"
}
```

---

**Validation:**

- user_id must have role = REFEREE  
- Event scheduling_mode must be INTER_ACADEMY and event_type must be LEAGUE or TOURNAMENT_MANAGED  

---

### Revoke Referee Assignment

DELETE /api/v1/events/{event_id}/referees/{assignment_id}

Roles: ADMIN.

---

### Assign Umpire to Table

POST /api/v1/events/{event_id}/umpires

Roles: ADMIN, assigned REFEREE for this event.

Only applicable to INTER_ACADEMY + LEAGUE and INTER_ACADEMY + TOURNAMENT_MANAGED events.

**Request:**
```json
{
  "user_id": "uuid-user-umpire-1",
  "table_number": 3
}
```

---

**Response (201):**
```json
{
  "assignment_id": "uuid-ump-assignment-1",
  "event_id": "uuid-event-1",
  "user_id": "uuid-user-umpire-1",
  "table_number": 3,
  "assigned_at": "2026-04-12T10:00:00Z"
}
```

---

**Validation:**

- user_id must have role = UMPIRE  
- table_number must not already have an active umpire assignment in this event (409 if conflict)  
- Event scheduling_mode must be INTER_ACADEMY and event_type must be LEAGUE or TOURNAMENT_MANAGED  

---

### Revoke Umpire Assignment

DELETE /api/v1/events/{event_id}/umpires/{assignment_id}

Roles: ADMIN, assigned REFEREE for this event.

---

## 6. Sessions

### Create Session

POST /api/v1/events/{event_id}/sessions

Roles: COACH of the host academy, ADMIN.

**Request:**
```json
{
  "session_date": "2026-04-14",
  "session_minutes": 150,
  "num_tables": 5,
  "match_format": "BEST_OF_3"
}
```

---

**Response (201):**
```json
{
  "session_id": "uuid-session-1",
  "event_id": "uuid-event-1",
  "session_date": "2026-04-14",
  "session_minutes": 150,
  "num_tables": 5,
  "match_format": "BEST_OF_3",
  "status": "SCHEDULED",
  "created_at": "2026-04-13T18:00:00Z"
}
```

---

### Generate Fixtures

POST /api/v1/sessions/{session_id}/generate-fixtures

Roles: COACH of the host academy, ADMIN.

Triggers the fixture generation algorithm. The system reads present players (from request body), determines the bootstrap phase, and writes FixtureSlot rows.

**Request:**
```json
{
  "present_player_ids": [
    "uuid-player-1", "uuid-player-2", "uuid-player-3",
    "uuid-player-4", "uuid-player-5", "uuid-player-6"
  ]
}
```

---

**Response (201):**
```json
{
  "session_id": "uuid-session-1",
  "bootstrap_phase": "STANDARD",
  "rating_spread": 312.0,
  "present_player_count": 20,
  "matches_per_player": 3,
  "rounds_generated": 3,
  "fixture_slots_created": 30,
  "generated_at": "2026-04-14T07:55:00Z"
}
```

---

**Validation:**

- Session must be in SCHEDULED status  
- All present_player_ids must be ACTIVE players registered to an academy in this event  
- Cannot regenerate fixtures once session is IN_PROGRESS or COMPLETED (returns 409)  

---

### Get Session Fixtures

GET /api/v1/sessions/{session_id}/fixtures

---

**Response (200):**
```json
{
  "session_id": "uuid-session-1",
  "session_date": "2026-04-14",
  "bootstrap_phase": "STANDARD",
  "matches_per_player": 3,
  "schedule": [
    {
      "round_number": 1,
      "sub_round": null,
      "time_slot": "07:00–07:25",
      "fixtures": [
        {
          "slot_id": "uuid-slot-1",
          "table_number": 1,
          "match_category": "COMPETITIVE",
          "player_a": {"player_id": "uuid-player-1", "name": "Aarav", "current_rating": 1460, "tier": "ELITE"},
          "player_b": {"player_id": "uuid-player-2", "name": "Priya", "current_rating": 1380, "tier": "ELITE"},
          "expected_rating_gap": 80,
          "status": "SCHEDULED",
          "match_id": null
        }
      ]
    },
    {
      "round_number": 2,
      "sub_round": null,
      "time_slot": "07:25–07:50",
      "fixtures": [
        {
          "slot_id": "uuid-slot-6",
          "table_number": 1,
          "match_category": "STRETCH",
          "player_a": {"player_id": "uuid-player-5", "name": "Riya", "current_rating": 1020, "tier": "INTERMEDIATE"},
          "player_b": {"player_id": "uuid-player-3", "name": "Vikram", "current_rating": 1180, "tier": "ADVANCED"},
          "expected_rating_gap": 160,
          "status": "PLAYED",
          "match_id": "uuid-match-12"
        }
      ]
    }
  ]
}
```

---

### Update Session Status

PATCH /api/v1/sessions/{session_id}/status

Roles: COACH, ADMIN.

**Request:**
```json
{
  "status": "COMPLETED"
}
```

---

## 7. Matches

### Submit Match Result

```

POST /api/v1/matches

```

Roles: PLAYER (own matches), COACH (any player in their academy), ADMIN, REFEREE (any match in their assigned event), UMPIRE (matches at their assigned table only).

For INTER_ACADEMY + LEAGUE and INTER_ACADEMY + TOURNAMENT_MANAGED events, the table umpire typically submits on behalf of both players.

**Request:**
```json
{
  "event_id": "uuid-event-1",
  "session_id": "uuid-session-1",
  "player_a_id": "uuid-player-1",
  "player_b_id": "uuid-player-2",
  "match_format": "BEST_OF_3",
  "sets_won_a": 2,
  "sets_won_b": 1,
  "is_retirement": false,
  "match_date": "2026-04-14",
  "match_timestamp": "2026-04-14T07:10:00Z"
}
```

---

**Request — retirement match:**
```json
{
  "event_id": "uuid-event-1",
  "session_id": null,
  "player_a_id": "uuid-player-3",
  "player_b_id": "uuid-player-4",
  "match_format": "BEST_OF_5",
  "sets_won_a": 3,
  "sets_won_b": 1,
  "sets_won_a_actual": 3,
  "sets_won_b_actual": 0,
  "is_retirement": true,
  "match_date": "2026-04-14",
  "match_timestamp": "2026-04-14T09:00:00Z"
}
```

sets_won_a/b contain the credited score (awarded sets included); sets_won_a/b_actual contain the physical sets at retirement.

---

**Response (201):**
```json
{
  "match_id": "uuid-match-1",
  "confirmation_status": "PENDING",
  "confirmation_deadline": "2026-04-14T23:59:59Z",
  "rating_eligible": true,
  "ratings_trigger": "DAILY_EOD",
  "message": "Awaiting confirmation from opponent. Ratings will be applied at end of day if confirmed."
}
```

ratings_trigger reflects the event's trigger mode: DAILY_EOD (INTRA_ACADEMY + FRIENDLY) or EVENT_COMPLETION (all INTER_ACADEMY combinations). When rating_eligible = false, not_eligible_reason is included instead.

**Validation:**

- event_id must reference an active event within its date range  
- Both players must be ACTIVE and registered in an academy in this event  
- player_a_id != player_b_id  
- player_id is internally normalized to min(player_a_id, player_b_id) for deduplication; the response reflects the normalized order  
- Set score must be valid for declared match_format:  
  - BEST_OF_3: one player has exactly 2 sets and the other has 0 or 1  
  - BEST_OF_5: one player has exactly 3 sets and the other has 0–2  
  - BEST_OF_7: one player has exactly 4 sets and the other has 0–3  
- Deduplication check: UNIQUE(player_a_id, player_b_id, event_id, match_date) — returns 409 if already exists  
- If abs(player_a_rating - player_b_rating) > rating_gap_max config value: match is accepted but rating_eligible = false, not_eligible_reason = RATING_GAP_EXCEEDED  
- Retirement with sets_won_a = 0 AND sets_won_b = 0: rating_eligible = false, not_eligible_reason = ZERO_SETS_RETIREMENT  
- Walkover: sets_won_a = 0 AND sets_won_b = 0 AND is_retirement = false: rating_eligible = false, not_eligible_reason = WALKOVER  

---

### Confirm Match Result

POST /api/v1/matches/{match_id}/confirm

Roles: PLAYER (the non-submitting player), COACH of the non-submitting player's academy, REFEREE (any match in their assigned event).

**Request — confirm:**
```json
{
  "confirmed": true
}
```

---

**Request — dispute:**
```json
{
  "confirmed": false,
  "dispute_reason": "Score was 2-1, not 2-0. I won the second set."
}
```

---

**Response (200) — confirmed:**
```json
{
  "match_id": "uuid-match-1",
  "confirmation_status": "CONFIRMED",
  "rating_eligible": true,
  "ratings_trigger": "DAILY_EOD",
  "ratings_applied_at": null,
  "message": "Match confirmed. Ratings will be applied at end of day."
}
```

Ratings are never applied synchronously at confirmation time. They are applied by the background scheduler:
- DAILY_EOD (INTRA_ACADEMY + FRIENDLY): at 23:59:59 on match_date  

- EVENT_COMPLETION (all INTER_ACADEMY combinations): when admin marks the event COMPLETED  

When ratings are eventually applied, ratings_applied_at is set on the match and a match_confirmed webhook fires with the actual rating updates. Poll GET /api/v1/matches/{match_id} or subscribe to webhooks for the final values.

---

**Response (200) — disputed:**
```json
{
  "match_id": "uuid-match-1",
  "confirmation_status": "DISPUTED",
  "dispute_id": "uuid-dispute-1",
  "resolution_deadline": "2026-04-17T23:59:59Z",
  "message": "Dispute raised. Rating update deferred until resolution."
}
```

---

### Get Match

GET /api/v1/matches/{match_id}

---

**Response (200):**
```json
{
  "match_id": "uuid-match-1",
  "event": {
    "event_id": "uuid-event-1",
    "name": "April Cross-Academy League — Mumbai North",
    "scheduling_mode": "INTER_ACADEMY",
    "event_type": "LEAGUE"
  },
  "session_id": "uuid-session-1",
  "player_a": {"player_id": "uuid-player-1", "name": "Aarav", "tier": "ELITE"},
  "player_b": {"player_id": "uuid-player-2", "name": "Priya", "tier": "ADVANCED"},
  "player_a_academy": {"academy_id": "uuid-academy-x", "name": "TT Academy X"},
  "player_b_academy": {"academy_id": "uuid-academy-y", "name": "TT Academy Y"},
  "umpire": {"user_id": "uuid-user-umpire-1", "name": "Rajan Kumar"},
  "match_format": "BEST_OF_5",
  "sets_won_a": 3,
  "sets_won_b": 0,
  "is_retirement": false,
  "winner_id": "uuid-player-1",
  "rating_eligible": true,
  "ratings_applied_at": "2026-03-28T20:15:00Z",
  "effective_event_type": "LEAGUE",
  "diminishing_signal_applied": false,
  "match_date": "2026-03-28",
  "confirmation_status": "CONFIRMED"
}
```

---

### Void Match

POST /api/v1/matches/{match_id}/void

Roles: ADMIN, or assigned REFEREE for the event this match belongs to (scoped to their event only).

**Request:**
```json
{
  "reason": "Misconduct reported by supervising coach"
}
```

---

**Response (200):**
```json
{
  "match_id": "uuid-match-1",
  "confirmation_status": "VOIDED",
  "rating_rollback": {
    "player_a": {
      "player_id": "uuid-player-1",
      "delta_reversed": -28,
      "rating_before_rollback": 1378,
      "rating_after_rollback": 1350
    },
    "player_b": {
      "player_id": "uuid-player-2",
      "delta_reversed": 28,
      "rating_before_rollback": 1222,
      "rating_after_rollback": 1250
    }
  }
}
```

**Behaviour:**

- Writes two new RatingHistory rows with is_rollback = true and rollback_of_history_id pointing to the original rows  
- Updates Player.current_rating atomically for both players  
- Does not recalculate subsequent matches  

---

## 8. Disputes

### List Disputes

GET /api/v1/disputes?status=OPEN&event_id=uuid-event-1&limit=20&offset=0

Roles: ADMIN (all disputes system-wide); REFEREE (disputes for their assigned event only — use event_id filter).

---

**Response (200):**
```json
{
  "disputes": [
    {
      "dispute_id": "uuid-dispute-1",
      "match_id": "uuid-match-1",
      "match_date": "2026-04-14",
      "players": [
        {"player_id": "uuid-player-1", "name": "Aarav"},
        {"player_id": "uuid-player-2", "name": "Priya"}
      ],
      "raised_by": {"user_id": "uuid-user-2", "name": "Priya Sharma"},
      "reason": "Score was 2-1, not 2-0.",
      "status": "OPEN",
      "resolution_deadline": "2026-04-17T07:10:00Z",
      "created_at": "2026-04-14T08:30:00Z"
    }
  ],
  "pagination": { "total": 3, "limit": 20, "offset": 0 }
}
```

---

### Get Dispute

GET /api/v1/disputes/{dispute_id}

Roles: ADMIN; REFEREE (for disputes in their assigned event); PLAYER or COACH (for disputes involving their own matches).

---

### Update Dispute Status

PATCH /api/v1/disputes/{dispute_id}/status

Roles: ADMIN, or assigned REFEREE for the event the disputed match belongs to.

**Request:**
```json
{
  "status": "UNDER_REVIEW"
}
```

---

### Resolve Dispute

POST /api/v1/disputes/{dispute_id}/resolve

Roles: ADMIN, or assigned REFEREE for the event the disputed match belongs to.

For INTER_ACADEMY + LEAGUE and INTER_ACADEMY + TOURNAMENT_MANAGED events the referee is the primary resolver. Their resolution is final and does not require further admin approval. An admin may only resolve if no referee is assigned or their assignment has been revoked.

**Request — confirm original score:**
```json
{
  "resolution": "CONFIRMED_ORIGINAL",
  "resolution_notes": "Video reviewed. Original score 2-0 confirmed."
}
```

---

**Request — correct score:**
```json
{
  "resolution": "CORRECTED",
  "corrected_sets_won_a": 2,
  "corrected_sets_won_b": 1,
  "resolution_notes": "Video reviewed. Actual score was 2-1."
}
```

---

**Request — void match:**
```json
{
  "resolution": "VOIDED",
  "resolution_notes": "Insufficient evidence to determine correct score."
}
```

---

**Response (200):**
```json
{
  "dispute_id": "uuid-dispute-1",
  "match_id": "uuid-match-1",
  "resolution": "CORRECTED",
  "rating_updates": {
    "player_a": {"rating_before": 1378, "rating_after": 1362, "delta": -16},
    "player_b": {"rating_before": 1222, "rating_after": 1238, "delta": 16}
  },
  "resolved_at": "2026-04-15T11:00:00Z"
}
```

**Behaviour for CORRECTED:**
1. Rolls back the original match delta via two is_rollback = true RatingHistory rows  
2. Re-runs the rating calculation with the corrected score  
3. Writes two new RatingHistory rows with the corrected delta  
4. Updates Player.current_rating atomically for both players  

---

## 9. Leaderboards and Analytics

### Global Leaderboard

GET /api/v1/leaderboards?tier=ELITE&limit=20&offset=0

---

**Response (200):**
```json
{
  "tier_filter": "ELITE",
  "players": [
    {
      "rank": 1,
      "player_id": "uuid-player-10",
      "name": "Aditya Rao",
      "current_rating": 1492,
      "tier": "ELITE",
      "primary_academy": {"academy_id": "uuid-academy-x", "name": "TT Academy X"},
      "rated_matches_completed": 74,
      "is_provisional": false
    }
  ],
  "pagination": { "total": 18, "limit": 20, "offset": 0 }
}
```

---

### Age-Group Leaderboard

GET /api/v1/analytics/leaderboard?age_group=U13&limit=20&offset=0

age_group values: U10, U13, U15, U17

---

**Response (200):**
```json
{
  "age_group": "U13",
  "as_of_jan1_year": 2026,
  "players": [
    {
      "rank": 1,
      "player_id": "uuid-player-10",
      "name": "Aditya Rao",
      "age_as_of_jan1": 12,
      "current_rating": 1420,
      "tier": "ELITE",
      "percentile_in_age_group": 97,
      "rating_velocity_30d": 35.2,
      "rated_matches_completed": 62
    }
  ],
  "pagination": { "total": 34, "limit": 20, "offset": 0 }
}
```

---

### Player Rating Velocity

GET /api/v1/analytics/players/{player_id}/velocity?period=3m

period values: 1m, 3m, 6m, 1y

---

**Response (200):**
```json
{
  "player_id": "uuid-player-10",
  "period": "3m",
  "period_start": "2026-01-12",
  "period_end": "2026-04-12",
  "rating_start": 1310,
  "rating_end": 1420,
  "delta": 110,
  "velocity_per_month": 36.7,
  "matches_played": 28,
  "win_rate": 0.68,
  "stretch_win_rate": 0.35,
  "tier_changes": [
    {"from": "ADVANCED", "to": "ELITE", "date": "2026-02-18"}
  ]
}
```

---

### Academy Season Report

GET /api/v1/analytics/academies/{academy_id}/report?season_id=uuid-season-1

Roles: COACH of that academy, ADMIN.

---

**Response (200):**
```json
{
  "academy_id": "uuid-academy-x",
  "season": {"season_id": "uuid-season-1", "name": "2026 Summer League"},
  "summary": {
    "active_players": 18,
    "total_rated_matches": 1340,
    "cross_academy_matches": 72,
    "avg_matches_per_player": 74.4,
    "confirmation_rate": 0.97,
    "dispute_rate": 0.02
  },
  "asi_trend": [
    {"week": "2026-06-07", "asi": 1155},
    {"week": "2026-06-14", "asi": 1162}
  ],
  "tier_distribution": {
    "BEGINNER": 2,
    "INTERMEDIATE": 5,
    "ADVANCED": 6,
    "ELITE": 4,
    "NATIONAL_TRACK": 1
  },
  "top_movers": [
    {"player_id": "uuid-player-5", "name": "Sneha Patel", "rating_delta": 142}
  ]
}
```

---

## 10. System Configuration

### Get Current Configuration

GET /api/v1/config

Roles: ADMIN (full values); COACH and PLAYER receive a read-only subset (tier boundaries, match weights).

---

**Response (200):**
```json
{
  "config": {
    "starting_rating_unseeded": "1000",
    "provisional_match_threshold": "15",
    "k_cap": "60",
    "w_match_league": "1.0",
    "w_match_tournament": "1.2",
    "w_match_friendly": "0.5",
    "w_academy_same": "0.8",
    "w_academy_cross": "1.2",
    "tier_beginner_max": "900",
    "tier_intermediate_max": "1100",
    "tier_advanced_max": "1300",
    "tier_elite_max": "1500",
    "global_average_rating": "1095"
  },
  "last_updated_at": "2026-04-07T00:00:00Z"
}
```

### Update Configuration

### PATCH /api/v1/config

Roles: ADMIN.

**Request:**
```json
{
  "w_match_tournament": "1.3",
  "friendly_weekly_cap": "3"
}
```

...

**Response (200):**
```json
{
  "updated_keys": ["w_match_tournament", "friendly_weekly_cap"],
  "effective_for_matches_after": "2026-04-12T15:30:00Z",
  "changed_by": "uuid-user-admin-1"
}
```

...

**Behaviour:** Each changed key produces one row in SystemConfigurationHistory. Changes apply only to matches submitted after effective_for_matches_after.

---

### Get Configuration History

...

GET /api/v1/config/history?key=w_match_tournament&limit=10

...

Roles: ADMIN.

**Response (200):**
```json
{
  "history": [
    {
      "history_id": "uuid-confhist-1",
      "key": "w_match_tournament",
      "old_value": "1.2",
      "new_value": "1.3",
      "changed_by": { "user_id": "uuid-admin-1", "name": "League Admin" },
      "changed_at": "2026-04-12T15:30:00Z",
      "effective_for_matches_after": "2026-04-12T15:30:00Z"
    }
  ],
  "pagination": { "total": 2, "limit": 10, "offset": 0 }
}
```

---

## 11. Webhooks

The system publishes events via HTTP POST to registered endpoints. Payloads are signed with HMAC-SHA256 using the `X-JLRS-Signature` header.

| Event | Trigger | Key Payload Fields |
|---|---|---|
| match.confirmed | Match confirmed or auto-confirmed | match_id, both player IDs, rating_updates |
| match.disputed | Dispute raised | match_id, dispute_id, reason, resolution_deadline |
| match.voided | Match voided | match_id, reason, rating_rollback |
| dispute.resolved | Dispute resolved | dispute_id, resolution, rating_updates |
| player.tier_changed | Player crosses a tier boundary | player_id, old_tier, new_tier, new_rating |
| player.provisional_complete | Player exits provisional phase | player_id, final_provisional_rating, tier |
| academy.asi_recalculated | Weekly ASI recalculation ran | academy_id, old_asi, new_asi, qualifying_player_count |
| session.fixtures_generated | Fixture generation completed | session_id, bootstrap_phase, fixture_slots_created |
| dispute.auto_expired | Dispute expired without resolution | dispute_id, match_id, resolution = VOIDED |

---

## Rate Limiting

| Role | General Limit | Match Submission Limit |
|---|---|---|
| PLAYER | 60 req/min | 20 submissions/day per player |
| COACH | 120 req/min | 20 submissions/day per player submitted on behalf of |
| ADMIN | 300 req/min | No additional limit |
| REFEREE | 120 req/min | No additional limit (submits on behalf of players during event) |
| UMPIRE | 60 req/min | 30 submissions/day (per-table throughput for a full event day) |

---

## Pagination

All list endpoints accept limit (max 100, default 20) and offset query parameters. All responses include a pagination object:

```json
{
  "pagination": {
    "total": 142,
    "limit": 20,
    "offset": 40
  }
}
```

---

## Error Response Format

All errors use a consistent envelope:

```json
{
  "error": {
    "code": "MATCH_DUPLICATE",
    "message": "A match between these players in this event on this date already exists.",
    "details": {
      "existing_match_id": "uuid-match-existing"
    }
  }
}
```

---

### HTTP Status Codes

| Status | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Validation error (bad input) |
| 401 | Authentication required |
| 403 | Insufficient permissions for this resource |
| 404 | Resource not found |
| 409 | Conflict (duplicate match, invalid state transition, quarterly academy change limit) |
| 422 | Semantically invalid request (e.g., retirement score with 0 physical sets but sets_won indicate play occurred) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

### Error Codes

| Code | Description |
|---|---|
| MATCH_DUPLICATE | Match already exists for this player pair, event, and date |
| MATCH_RATING_GAP_EXCEEDED | Match accepted but not rated — gap exceeds rating_gap_max |
| MATCH_INVALID_SET_SCORE | Set score is not valid for the declared format |
| MATCH_NOT_CONFIRMABLE | Match is not in PENDING status |
| PLAYER_NOT_IN_EVENT_ACADEMY | Player's academy is not registered for this event |
| EVENT_TYPE_LOCKED | event_type and scheduling_mode cannot be changed after event status transitions to IN_PROGRESS |
| ACADEMY_TRANSFER_TOO_SOON | Player has already transferred academies this quarter |
| ACADEMY_TRANSFER_INVALID_DATE | effective_date must be the 1st of a future month |
| DISPUTE_WINDOW_CLOSED | Dispute must be raised within 48 hours of match submission |
| DISPUTE_ALREADY_ACTIVE | This match already has an open dispute |
| SESSION_FIXTURES_ALREADY_GENERATED | Cannot regenerate fixtures for an in-progress or completed session |
| CONFIG_KEY_UNKNOWN | The configuration key does not exist |
| INSUFFICIENT_PERMISSIONS | Role does not have access to this operation |