# JLRS Implementation Plan

## Context

The Junior League Rating System (JLRS) is a continuous, match-driven rating platform for junior table tennis players across training academies. It replaces episodic official rankings with a real-time Elo-based system that captures every match — within academies (daily training sessions) and across them (monthly league meets and tournaments).

All design documents, data model, API contract, edge case catalog, fixture algorithm, and PostgreSQL DDL (24 files in `sql/`) are complete. This plan covers only the implementation.

---

## Confirmed Choices

| Decision | Choice |
|---|---|
| Backend framework | FastAPI (already in `requirements.txt`) |
| Database access | Raw SQL via psycopg2 (no ORM) |
| Migrations | None — DDL files in `sql/` are run manually once at deployment |
| Frontend | React + Vite + PWA (follow-on sprint) |
| Sprint order | Backend-first: all 7 backend phases before frontend |
| Python version | 3.13.3 |
| Deployment | Railway PaaS |

---

## How Configuration and JWT Work

### `app/config.py` — Pydantic BaseSettings

Pydantic `BaseSettings` is a class that reads your application's configuration from **environment variables** at startup — not from a config file. In Railway, you set environment variables in the service's "Variables" panel (e.g., `DATABASE_URL`, `JWT_SECRET`). When the FastAPI app starts, Pydantic reads those variables and makes them available as typed Python attributes.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str         # e.g., postgresql://user:pass@host:5432/dbname
    jwt_secret: str           # e.g., a long random string you generate once
    jwt_expiry_hours: int = 24
    frontend_url: str         # e.g., https://jlrs.railway.app (for CORS)
    webhook_secret: str       # for signing webhook payloads with HMAC-SHA256
    internal_job_secret: str  # protects internal cron endpoints from public access

settings = Settings()
```

Railway automatically injects `DATABASE_URL` when you link the Postgres plugin to the API service. All other variables you add manually in the Railway dashboard once.

### JWT Auth Flow

JWT (JSON Web Token) is a signed token that proves identity without server-side session storage.

**Login flow:**
1. User POSTs email + password to `POST /api/v1/auth/login`
2. Server verifies password against `password_hash` in DB
3. Server creates a JWT: `{ "user_id": "...", "role": "COACH", "exp": <24h from now> }` signed with `JWT_SECRET` using HS256 algorithm
4. JWT returned to client — client stores it (in memory or `localStorage`)

**Authenticated request flow:**
1. Client sends every request with header: `Authorization: Bearer <token>`
2. FastAPI dependency `get_current_user` intercepts the request, extracts the token, verifies the signature using `JWT_SECRET`, checks expiry
3. If valid: injects the user object into the route handler. If invalid/expired: returns 401.

No database lookup is needed on every request — the token itself contains the user_id and role, signed so it cannot be tampered with. The `JWT_SECRET` must never be exposed.

---

## Railway Architecture (Cost-Optimised)

Two Railway services (not three), one Postgres plugin:

```
Railway Project: jlrs
├── Service: api       — FastAPI, Gunicorn + Uvicorn workers
│                        + internal cron endpoints (called by Railway Crons)
├── Plugin:  postgres  — Railway managed PostgreSQL
└── Service: web       — React Vite PWA, nginx static (follow-on)
```

**No separate scheduler service.** Instead, use **Railway Crons** (built into Railway, no extra cost) to call internal HTTP endpoints on the `api` service on a schedule. The `api` service already runs 24/7 for incoming requests — the cron calls are just additional HTTP requests to endpoints that are already there.

Internal cron endpoints are protected by a shared secret (`INTERNAL_JOB_SECRET`). Railway Crons sends this in the request header; the endpoint rejects any call without it. These endpoints are not listed in the public API docs.

### Cron Schedule (Minimised)

Instead of running jobs every 5 or 15 minutes, all daily work is consolidated into **one nightly run**:

| Railway Cron | IST Time | What it does |
|---|---|---|
| Daily — `58 23 * * *` | 23:58 IST | 1. Auto-confirm all matches whose deadline has passed. 2. Expire disputes >72h old (void them). 3. Apply EOD ratings for INTRA_ACADEMY + FRIENDLY matches. 4. Recalculate ASI for all academies. |
| Weekly — `0 0 * * 0` | 00:00 IST Sunday | Check inactivity: freeze academies where all players inactive ≥ 8 weeks. |

**Why 23:58 not 23:59:30?** The confirmation deadline is end of match day (23:59:59). Running at 23:58 auto-confirms all pending matches whose deadline is that same day (deadline = 23:59:59 of match_date, not a rolling 48h). Then the EOD rating job immediately processes the now-confirmed matches. Two minutes of buffer is sufficient.

**INTER_ACADEMY events (LEAGUE + TOURNAMENT):** These are triggered by the admin marking the event COMPLETED via `PATCH /api/v1/events/{id}/status` — this is a user action, not a cron job. No scheduled job needed for this at all.

**Dispute expiry for INTER_ACADEMY events:** Disputes expire at 72h. The nightly cron handles this for intra-academy disputes. For inter-academy disputes, the event COMPLETED endpoint checks for open disputes and rejects the transition (returns 409). The admin must resolve or wait for the nightly expiry. This is correct per the spec.

---

## Requirements Changes

Remove from `requirements.txt`:
- `sqlalchemy==2.0.28` — no ORM, using raw psycopg2 instead
- `alembic==1.13.1` — no migrations system needed

Keep and update to latest versions:
```
fastapi==0.115.12
uvicorn[standard]==0.34.2
pydantic==2.11.3
pydantic-settings==2.9.1
python-jose[cryptography]==3.4.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.20
psycopg2-binary==2.9.10
httpx==0.28.1
pytest==8.3.5
ruff==0.11.6
black==25.1.0
```

Add:
```
cachetools==5.5.2
structlog==25.1.0
slowapi==0.1.9
```

---

## Project Structure

```
c:\rallypoint\
├── app/
│   ├── main.py                    # FastAPI app factory, CORS, error handlers, lifespan
│   ├── config.py                  # Pydantic BaseSettings (reads Railway env vars)
│   ├── database.py                # psycopg2 ThreadedConnectionPool, get_connection()
│   │
│   ├── routers/                   # FastAPI APIRouter per resource group
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── players.py
│   │   ├── academies.py
│   │   ├── seasons.py
│   │   ├── events.py
│   │   ├── sessions.py
│   │   ├── matches.py
│   │   ├── disputes.py
│   │   ├── leaderboard.py
│   │   ├── config.py
│   │   └── internal.py            # Internal cron endpoints (protected by INTERNAL_JOB_SECRET)
│   │
│   ├── services/
│   │   ├── auth_service.py        # Password verify, JWT create/decode
│   │   ├── player_service.py
│   │   ├── match_service.py       # Submit, confirm, void lifecycle
│   │   ├── dispute_service.py
│   │   ├── rating_engine.py       # Batch Elo computation, atomicity, rollback
│   │   ├── fixture_engine.py      # Three-phase bootstrap + Phase C pairing
│   │   ├── asi_service.py         # ASI recalculation
│   │   ├── leaderboard_service.py
│   │   └── webhook_service.py
│   │
│   ├── jobs/                      # Job functions called by internal cron endpoints
│   │   ├── daily_job.py           # Auto-confirm + dispute expiry + EOD ratings + ASI recalc
│   │   └── weekly_job.py          # Inactivity check + academy freeze
│   │
│   ├── dependencies/
│   │   ├── auth.py                # get_current_user, role_required
│   │   └── pagination.py
│   │
│   └── utils/
│       ├── rating_math.py         # Pure functions: K-factor, CR, expected_score, etc.
│       └── timezone.py            # IST helpers, EOD deadline computation
│
├── schemas/                       # Pydantic request/response schemas (separate from app/)
│   ├── auth.py
│   ├── player.py
│   ├── academy.py
│   ├── event.py
│   ├── session.py
│   ├── match.py
│   ├── rating.py
│   ├── dispute.py
│   └── leaderboard.py
│
├── tests/
│   ├── conftest.py                # DB fixtures pointing to test DB
│   ├── unit/
│   │   ├── test_rating_math.py    # Pure formula tests
│   │   └── test_fixture_engine.py
│   └── integration/
│       ├── test_match_flow.py
│       ├── test_rating_engine.py
│       └── test_dispute_flow.py
│
├── sql/                           # Existing DDL — run once at deployment
├── Dockerfile
├── railway.toml                   # Start command + cron configuration
└── requirements.txt
```

### Database Access Pattern (No ORM)

`app/database.py` creates a `psycopg2.pool.ThreadedConnectionPool` on startup. A context manager `get_connection()` checks out a connection, yields it, and returns it to the pool on exit. All SQL is written as parameterised strings — never concatenated with user input.

```python
from contextlib import contextmanager
import psycopg2.pool

_pool: psycopg2.pool.ThreadedConnectionPool = None

def init_pool(database_url: str):
    global _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10, dsn=database_url)

@contextmanager
def get_connection():
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
```

Services use it like:
```python
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM player WHERE player_id = %s AND status = 'ACTIVE'",
            (player_id,)
        )
        row = cur.fetchone()
```

The pool is initialised once in `app/main.py`'s lifespan handler and shared across all requests.

---

## Phase Breakdown

---

### Phase 1 — Foundation & Infrastructure (Week 1–2)

**Goal**: Runnable API with auth, DB, and all CRUD. No business logic yet.

**Deliverables**:

1. `app/config.py` — Pydantic BaseSettings for `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRY_HOURS`, `FRONTEND_URL`, `WEBHOOK_SECRET`, `INTERNAL_JOB_SECRET`
2. `app/database.py` — psycopg2 `ThreadedConnectionPool` with `get_connection()` context manager
3. `app/main.py` — FastAPI app factory:
   - Lifespan context: call `init_pool(settings.database_url)` on startup, close pool on shutdown
   - CORS middleware: `allow_origins=[settings.frontend_url]`
   - Global exception handlers (IntegrityError → 409, not-found → 404, unhandled → 500)
   - Include all routers under `/api/v1`
4. JWT auth:
   - `app/services/auth_service.py` — `create_token(user_id, role) -> str`, `decode_token(token) -> dict`
   - `app/dependencies/auth.py` — `get_current_user` FastAPI dependency: extracts Bearer token, calls `decode_token`, queries DB for user, returns user dict
   - `role_required(*roles)` — dependency factory that wraps `get_current_user` and raises 403 if caller's role is not in allowed list
   - `POST /api/v1/auth/login` — validates email + password, returns JWT
5. CRUD routers with full request validation and role enforcement:
   - Users: `POST /api/v1/users`, `GET /api/v1/users/{id}`
   - Academies: `POST /api/v1/academies`, `GET /api/v1/academies/{id}`
   - Players: `POST /api/v1/players`, `GET /api/v1/players/{id}`, `GET /api/v1/players/{id}/computed-stats`, `GET /api/v1/players/{id}/academy-history`, `PATCH /api/v1/players/{id}/academy`
   - Seasons: `POST /api/v1/seasons`, `GET /api/v1/seasons`, `PATCH /api/v1/seasons/{id}/status`
   - Events: `POST /api/v1/events`, `GET /api/v1/events/{id}`, `POST /api/v1/events/{id}/academies`, `PATCH /api/v1/events/{id}/status`, `POST /api/v1/events/{id}/referees`, `POST /api/v1/events/{id}/umpires`
6. `GET /api/v1/players/{id}/computed-stats` — fully computed (never stored):
   - `tier` — from rating thresholds (BEGINNER <900, INTERMEDIATE 900–1099, ADVANCED 1100–1299, ELITE 1300–1499, NATIONAL_TRACK 1500+)
   - `confidence_ratio` — `1 - exp(-(rated_matches + virtual_matches) / 30)`
   - `is_provisional` — seeding_level = UNSEEDED AND (rated_matches + virtual_matches) < 15
   - `weeks_inactive` — `(today - last_match_date).days / 7`
   - `age_as_of_jan1` — year difference as of January 1 of current year
7. `Dockerfile` (Python 3.13-slim, Gunicorn + Uvicorn workers) and `railway.toml`
8. `GET /api/v1/health` — returns DB ping status

**Tests**:
- Parametrized computed-stats: tier at ratings 899/900/1099/1100/1299/1300/1499/1500; CR at n=0/5/15/30/100; provisional at 14/15 matches
- Auth: wrong password → 401; expired token → 401; wrong role → 403; valid token → 200
- Academy constraint: COACH without academy_id → 422

**Critical files**: `app/config.py`, `app/database.py`, `app/main.py`, `app/services/auth_service.py`, `app/dependencies/auth.py`

---

### Phase 2 — Match Lifecycle (Week 3–4)

**Goal**: Full submit → confirm → dispute → void flow, without rating updates.

**Deliverables**:

1. `POST /api/v1/matches` — match submission:
   - **Canonical ordering**: if `player_a_id > player_b_id` (lexicographic UUID comparison), swap IDs and swap set scores before persisting. This is required for the DB unique constraint `(player_a_id, player_b_id, event_id, match_date)` to correctly deduplicate.
   - **Confirmation deadline**: `match_date` at `23:59:59 Asia/Kolkata`, stored as UTC using `zoneinfo.ZoneInfo("Asia/Kolkata")` (Python 3.13 stdlib, no pytz)
   - **Eligibility checks**: walkover (0-0, not retirement) → `not_eligible_reason = WALKOVER`; retirement with 0 physical sets → `ZERO_SETS_RETIREMENT`; `abs(rating_a - rating_b) > 500` → `RATING_GAP_EXCEEDED` (use raw current_ratings, not ASI-adjusted)
   - **Diminishing signal**: query for same (player_a, player_b) pair in last 7 days; if count ≥ 2, set `diminishing_signal_applied = TRUE`
   - **Dedup**: unique constraint violation → 409 with `MATCH_DUPLICATE` code
   - **Set score validation**: per match_format (Bo3: winner has exactly 2; Bo5: exactly 3; Bo7: exactly 4)
   - Returns: `match_id`, `confirmation_status = PENDING`, `confirmation_deadline`, `rating_eligible`, `ratings_trigger`

2. `POST /api/v1/matches/{id}/confirm` — with `confirmed: true` → sets `CONFIRMED`, records `confirmed_by`, `confirmed_at`. With `confirmed: false` + `dispute_reason` → creates Dispute row, sets match to `DISPUTED`.

3. Dispute endpoints:
   - `GET /api/v1/disputes` — paginated, filtered by status/event_id
   - `GET /api/v1/disputes/{id}`
   - `PATCH /api/v1/disputes/{id}/status` → UNDER_REVIEW
   - `POST /api/v1/disputes/{id}/resolve` — three resolutions:
     - `CONFIRMED_ORIGINAL`: close dispute, no score change
     - `CORRECTED`: update sets_won_a/b on match, re-evaluate rating_eligible; ratings applied at next EOD/event-completion
     - `VOIDED`: set match voided_at + void_reason; rollback ratings if already applied (Phase 3 stub)

4. `POST /api/v1/matches/{id}/void` — ADMIN/REFEREE only. Rollback stub for now.

5. Webhook service stub: `webhook_service.fire(event_type, payload)` logs but does not yet deliver.

**Non-obvious**: The `player_a_id < player_b_id` canonical ordering must also be applied when querying matches (the diminishing signal check must search with the canonical ordering of the two player IDs, not the order they were submitted).

**Critical files**: `app/services/match_service.py`, `app/routers/matches.py`, `app/routers/disputes.py`

**Tests**:
- All eligibility scenarios: walkover, retirement 0 sets, retirement 1+ sets, gap 499, gap 500, gap 501
- Canonical ordering: submit with player_b > player_a, verify DB stores them in canonical order with swapped scores
- Dedup: same match twice → 409
- Confirmation deadline: verify UTC storage correct for IST midnight boundary
- Dispute state machine: OPEN → UNDER_REVIEW → RESOLVED; invalid transitions → 400

---

### Phase 3 — Rating Engine (Week 5–6)

**Goal**: Core Elo calculation with atomic batch application, EOD trigger, event-completion trigger, and rollback.

**Deliverables**:

1. `app/utils/rating_math.py` — pure functions, zero DB dependencies, fully unit-testable:
   - `get_k_base(rated_matches: int) -> float` — 50 if <30, 32 if 30–99, 20 if ≥100
   - `get_match_weight(effective_event_type: str) -> float` — LEAGUE=1.0, TOURNAMENT_EXTERNAL/MANAGED=1.2, FRIENDLY=0.5
   - `get_academy_weight(same_academy: bool) -> float` — 0.8 same, 1.2 cross
   - `get_cr(total_matches: int) -> float` — `1 - exp(-total_matches / 30)`
   - `get_k_eff(k_base, w_match, w_academy, cr) -> float` — `min(k_base * w_match * w_academy * (2 - cr), 60)`
   - `get_k_shared(k_eff_a, k_eff_b) -> float` — `(k_eff_a + k_eff_b) / 2`
   - `get_expected_score(r_adj_a, r_adj_b) -> float` — `1 / (1 + 10 ** ((r_adj_b - r_adj_a) / 400))`
   - `get_actual_score(sets_winner, sets_loser, match_format) -> tuple[float, float]` — margin-of-victory tables from spec
   - `get_age_bonus(winner_dob: date, loser_dob: date, is_upset: bool) -> float` — `min(10, 2 * age_diff_years)`, only when `is_upset = True`; age_diff = floor((winner_dob - loser_dob).days / 365.25); bonus only if younger player won
   - `get_asi_adjusted_rating(player_rating, global_avg, asi) -> float` — `player_rating + (global_avg - asi)`
   - `get_effective_event_type(event_type, diminishing_signal_applied) -> str` — returns FRIENDLY if diminishing_signal_applied else event_type

2. `app/services/rating_engine.py` — `apply_ratings_batch(conn, match_ids: list[str]) -> None`:
   ```
   Within ONE DB transaction (single connection, no commit until end):
   1. SELECT FOR UPDATE all player rows involved — prevents double-apply
   2. Load system_configuration values (from TTLCache, 60s TTL)
   3. Load latest AcademyASIHistory asi_value for each affected academy
      - If NULL (DEFAULTED) → use global_average_rating config value
   4. Load global average rating from config (updated by nightly ASI job)
   5. Process each match in match_timestamp ASC order:
      a. get_effective_event_type (diminishing_signal → FRIENDLY)
      b. get_asi_adjusted_rating for both players
      c. get_expected_score(r_adj_a, r_adj_b)
      d. is_upset = winner's R_adj < loser's R_adj
      e. get_actual_score from sets_won_a/b (credited, not actual)
      f. get_k_base for each player; get_cr for each player
      g. get_k_eff for each player using w_match, w_academy, cr
      h. get_k_shared
      i. delta = k_shared * (actual_score_winner - expected_score_winner)
      j. get_age_bonus (only if is_upset and younger player won)
      k. winner_new_rating = winner_rating + delta + age_bonus
         loser_new_rating  = loser_rating  - delta - age_bonus
      l. Write RatingHistory row for each player with full delta_breakdown JSONB
      m. Update player.current_rating, player.rated_matches_completed, player.last_match_date
      n. Set match.ratings_applied_at = NOW()
   6. Recalculate ASI: compute mean current_rating of qualifying players per affected academy;
      insert new AcademyASIHistory row
   7. Update global_average_rating in system_configuration
   8. COMMIT — ratings_applied_at only persisted on success
   9. After commit: check for tier changes (compare tier_before vs tier_after in RatingHistory);
      fire tier-change webhooks
   ```

3. `rollback_match(conn, match_id: str) -> None`:
   - Reads RatingHistory rows for match where `is_rollback = FALSE`
   - Writes new rows with negated deltas, `is_rollback = TRUE`, `rollback_of_history_id` pointing to originals
   - Updates `player.current_rating` for both players
   - Does NOT recalculate subsequent matches (per edge case catalog §1.4)

4. `PATCH /api/v1/events/{id}/status → COMPLETED`:
   - Check for open disputes — 409 if any (with list of open dispute IDs)
   - Query eligible INTER_ACADEMY matches for the event: `rating_eligible = TRUE AND ratings_applied_at IS NULL AND confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')`
   - Call `apply_ratings_batch(conn, match_ids)`
   - Set `event.status = COMPLETED`

5. Wire `POST /api/v1/matches/{id}/void` to call `rollback_match` if `ratings_applied_at IS NOT NULL`

6. Dispute resolve with CORRECTED: rollback original delta, re-run rating calculation with corrected scores, write new RatingHistory rows

**Non-obvious decisions**:
- **Gap > 500 uses raw ratings at submission time**: Evaluated and stored as `not_eligible_reason` on the match row. Never re-evaluated at rating time.
- **Upset detection uses R_adj** (after ASI normalization): The expected score is computed on adjusted ratings. If `expected_score < 0.5` (i.e., winner's R_adj was lower), it's an upset.
- **Diminishing signal**: match is still rated and still counts toward rated_matches_completed. Only the effective_event_type changes to FRIENDLY (halving the K weight from 1.0 to 0.5). It is NOT ineligible.
- **SELECT FOR UPDATE**: Locks player rows for the duration of the transaction. Combined with the nightly cron being a single HTTP call (not concurrent), this prevents double-apply even if the cron fires twice.

**Critical files**: `app/utils/rating_math.py`, `app/services/rating_engine.py`

**Tests**:
- Unit: all `rating_math.py` functions with boundary values
- Table-driven: all margin-of-victory scenarios (Bo3: 2-0, 2-1; Bo5: 3-0, 3-1, 3-2; Bo7: 4-0, 4-1, 4-2, 4-3)
- Table-driven: K-factor at rated_matches 0, 29, 30, 99, 100
- Integration: full jlrs.md worked example (Player A 1350, Player B 1250, cross-academy tournament, 3-0, age 11 vs 13) — assert final ratings 1378 and 1222 ± 0.5
- Integration: `ratings_applied_at IS NULL` predicate — run batch twice, assert RatingHistory has exactly 2 rows
- Integration: rollback — apply ratings, void match, assert player ratings restored exactly

---

### Phase 4 — Fixture Engine (Week 7)

**Goal**: Three-phase bootstrap algorithm generating FixtureSlot rows.

**Deliverables**:

1. `app/services/fixture_engine.py` — pure Python functions (no DB access, fully unit-testable):
   - `detect_phase(players: list[dict]) -> str` — computes `max_rating - min_rating`; DISCOVERY (<100), TRANSITION (100–249), STANDARD (≥250)
   - `calculate_session_capacity(session_minutes, num_tables, match_format) -> dict` — formula from spec, matches_per_player capped at 4
   - `generate_discovery_fixtures(players, round_offset) -> list[dict]` — circle-method round-robin. `round_offset` = count of prior sessions under the event (fetched by router, passed in). Odd player count: add BYE sentinel.
   - `generate_transition_fixtures(players) -> list[dict]` — median split; within-half competitive (adjacent pairs); cross-half stretch/anchor
   - `generate_standard_fixtures(players, recent_match_pairs: set[tuple]) -> list[dict]`:
     - Sort players by rating descending
     - Competitive rounds: adjacent pairs within tier; odd tier → borderline pair to nearest adjacent tier
     - Stretch round: fold by `k` pairs with `k + floor(N/4)`. Gap filter: <100 → COMPETITIVE, >250 → find next eligible. Skip pairs in `recent_match_pairs`.
     - BYE for odd total players (rotating)
   - All functions return list of slot dicts; router layer writes to DB

2. `POST /api/v1/events/{id}/sessions` — create session (validate event is INTRA_ACADEMY)
3. `POST /api/v1/sessions/{id}/generate-fixtures` — COACH/ADMIN:
   - Fetch player objects with current ratings
   - Fetch recent_match_pairs: `(player_a_id, player_b_id)` pairs from last 7 days
   - Fetch round_offset: `COUNT(*) FROM session WHERE event_id = :event_id AND session_date < :this_session_date`
   - Call fixture engine dispatcher
   - Persist FixtureSlot rows with canonical player ordering
   - Returns: bootstrap_phase, matches_per_player, fixture_slots_created
4. `GET /api/v1/sessions/{id}/fixtures` — returns schedule grouped by round, with player names, ratings, match categories, expected gaps, and status (SCHEDULED/PLAYED/UNPLAYED/BYE)
5. `PATCH /api/v1/sessions/{id}/status`

**Critical files**: `app/services/fixture_engine.py`, `app/routers/sessions.py`

**Tests**:
- Unit: phase detection at spreads 99/100/249/250
- Unit: circle-method for N=8, N=16, N=20 players — verify no self-pairings, no duplicate pairs in one full rotation
- Unit: capacity formula for all session configurations in spec
- Unit: folded pairing gap filter; BYE for odd count
- Unit: dedup — recent_match_pairs excludes those pairs from stretch round
- Integration: `generate-fixtures` for 20 players → verify slot count = 30, COMPETITIVE ≥ 50% of slots, no self-pairings

---

### Phase 5 — Analytics, Leaderboards, ASI (Week 8)

**Goal**: All remaining read endpoints and analytics aggregates.

**Deliverables**:

1. `GET /api/v1/leaderboard?tier=&limit=&offset=` — raw SQL with `ROW_NUMBER() OVER (ORDER BY current_rating DESC)`. Uses `idx_player_rating` DDL index.
2. `GET /api/v1/academies/{id}/leaderboard?tier=&limit=&offset=` — filtered by `primary_academy_id`. Uses `idx_player_academy_rating` DDL index.
3. `GET /api/v1/analytics/leaderboard?age_group=U13` — age as of January 1 of current year. U11 (≤11), U13 (12–13), U15 (14–15), U17 (16–17). Percentile: `PERCENT_RANK() OVER (ORDER BY current_rating)` within the age group.
4. `GET /api/v1/analytics/players/{id}/velocity?period=1m|3m|6m|1y` — aggregate from RatingHistory: start rating, end rating, matches played, win rate, stretch win rate (match_category = STRETCH), tier changes
5. `GET /api/v1/analytics/academies/{id}/report?season_id=` — total rated matches, cross-academy %, confirmation rate, ASI trend (from AcademyASIHistory), tier distribution, top movers (highest delta in period)
6. `GET /api/v1/academies/{id}/asi-history?limit=12`
7. `GET /api/v1/players/{id}/rating-history?limit=&offset=` — conditional `delta_breakdown` visibility (only for the player themselves, their coach, or admin)
8. `GET /api/v1/config` — full to ADMIN; read-only subset (tier boundaries, match weights) to COACH/PLAYER
9. `PATCH /api/v1/config` — ADMIN only; writes SystemConfigurationHistory row; invalidates TTLCache
10. `GET /api/v1/config/history?key=&limit=`

**Daily job additions** (`app/jobs/daily_job.py`):
- ASI recalculation after EOD ratings: for each ACTIVE academy, count qualifying players (≥15 rated matches, last match ≤ 8 weeks, status = ACTIVE); if ≥5 → COMPUTED; if academy FROZEN → FROZEN (copy last value); if <5 → DEFAULTED. Insert AcademyASIHistory row. Update `global_average_rating` in SystemConfiguration.

**Weekly job** (`app/jobs/weekly_job.py`):
- Find academies where all ACTIVE players have `last_match_date < NOW() - 56 days` (8 weeks); set `academy.status = FROZEN`, insert AcademyStatusHistory row.

**Internal cron endpoint** (`app/routers/internal.py`):
```
POST /internal/jobs/daily    — validates INTERNAL_JOB_SECRET header, calls daily_job.run()
POST /internal/jobs/weekly   — validates INTERNAL_JOB_SECRET header, calls weekly_job.run()
```
Railway Crons calls these on schedule. Returns 200 with job summary JSON, or 500 on failure (Railway logs alert).

**Critical files**: `app/services/leaderboard_service.py`, `app/jobs/daily_job.py`, `app/routers/internal.py`

**Tests**:
- Integration: leaderboard with 10 seeded players; verify rank column matches expected order
- Integration: age-group filter; verify only players in correct bracket returned
- Integration: ASI recalc with 3 players → DEFAULTED; 5 players → COMPUTED
- Integration: weekly job → academy FROZEN when all players inactive 8+ weeks
- Security: internal endpoint without correct secret → 403

---

### Phase 6 — Webhooks, OTP, Rate Limiting, Hardening (Week 9)

**Goal**: Production-ready security, OTP auth, webhook delivery, rate limiting, structured logging.

**Deliverables**:

1. OTP flow:
   - `POST /api/v1/auth/request-otp` — generate 6-digit code, store bcrypt-hashed in DB with `expires_at = NOW() + 10 minutes`, send via Resend email API
   - `POST /api/v1/auth/login` with `otp_code` — validate OTP against hash, check expiry, delete OTP row, return JWT

2. `app/services/webhook_service.py`:
   - `fire(event_type: str, payload: dict)` — constructs JSON body, signs with `HMAC-SHA256(WEBHOOK_SECRET, body)`, sends via `httpx.post()` with 3s timeout, logs result (fire-and-forget: does not raise on failure)
   - Called after commit, never before
   - Events: `match.confirmed`, `match.disputed`, `match.voided`, `dispute.resolved`, `dispute.auto_expired`, `player.tier_changed`, `player.provisional_complete`, `academy.asi_recalculated`, `session.fixtures_generated`

3. `slowapi` rate limiting:
   - `POST /auth/login`: 5/min per IP
   - `POST /auth/request-otp`: 3/min per IP
   - Match submission: per-role limits from API contract

4. `structlog` JSON logging: request middleware injects `request_id` (UUID) into every log entry; errors include stack trace. Railway drains this as structured JSON.

5. Global exception handler in `app/main.py`:
   - `psycopg2.errors.UniqueViolation` → 409 with correct error code
   - `psycopg2.errors.ForeignKeyViolation` → 422
   - `ValueError` from service layer → 400
   - Unhandled → 500 with `request_id` in response for support

**Tests**:
- OTP: valid code → JWT; expired code → 401; wrong code → 401; reuse after success → 401
- Webhook: mock HTTP receiver; verify `X-JLRS-Signature` header matches HMAC of body
- Rate limit: 6th login attempt → 429

---

### Phase 7 — Frontend: React + Vite PWA (Weeks 10–12)

**Tech stack**:

| Library | Version | Purpose |
|---|---|---|
| React | 19 | Component framework |
| TypeScript | 5.8 | Type safety |
| Vite | 6.3 | Build tool |
| vite-plugin-pwa | latest | PWA manifest + service worker + offline shell |
| Tailwind CSS | 4 | Utility-first styling |
| shadcn/ui | latest | Headless component primitives |
| TanStack Query | v5 | Data fetching, background refetch, optimistic updates |
| React Router | v7 | Client-side routing + route guards |
| Recharts | v2 | Analytics charts |
| Zod | v3 | Client-side validation mirroring backend schemas |

**Route structure**:
```
/                    → redirect to /leaderboard (public)
/leaderboard         → global leaderboard, no auth required
/login               → password + OTP auth
/dashboard           → COACH: roster, analytics, fixture generation
/match/submit        → mobile-first match submission
/match/:id/confirm   → confirm or dispute pending match
/player/:id          → rating card + history (own: full breakdown; others: summary)
/admin               → ADMIN: dispute queue, config, academies, seasons
```

**Player view** (mobile-first, ≥48px touch targets):
- Rating card: current rating, tier badge, CR progress bar, provisional countdown
- Today's session fixtures (from `GET /sessions/{id}/fixtures`)
- Match history: paginated list, delta chips, confirm/dispute buttons on PENDING matches

**Coach dashboard**:
- Roster table: rating, tier, last-active, CR, provisional flag
- Fixture generation wizard: date picker → attendance checkboxes → generate → printable fixture sheet
- Match submission form with player autocomplete, set score stepper (prevents invalid scores), retirement toggle
- Analytics: rating velocity line chart (per player or academy), tier distribution donut, age-group leaderboard tabs, stretch win rate card, ASI trend

**Admin panel**:
- Dispute queue: filterable by status, deadline countdown, inline resolve modal
- System configuration editor: key-value form with descriptions, change history
- Academy management: status chips, CRUD
- Season management: create, activate, view events

**PWA**: Offline shell cache for route skeletons; push notification permission prompt on first login for match confirmation alerts.

**Railway deployment**: `vite build` → `dist/` served by nginx static service.

**Tests**:
- Playwright E2E: coach login → generate fixtures → submit match → confirm as player → verify leaderboard updates
- Lighthouse CI: mobile performance ≥ 85, accessibility ≥ 90

---

## Verification (End-to-End After Each Phase)

Test using FastAPI's `/docs` interactive interface or `httpx` scripts:

**Phase 1**: Register academy → register player → `GET /players/{id}/computed-stats` (tier=INTERMEDIATE, CR≈0, provisional=true)

**Phase 2**: Create INTRA_ACADEMY+FRIENDLY event → submit match → confirm as opponent → verify match status = CONFIRMED

**Phase 3**: Manually trigger `POST /internal/jobs/daily` → verify RatingHistory rows created → verify delta matches jlrs.md worked example (±0.5 points)

**Phase 4**: Create session → `POST /sessions/{id}/generate-fixtures` with 20 players → verify 30 slots, 50% competitive

**Phase 5**: `GET /leaderboard` → verify rank order; `GET /analytics/players/{id}/velocity?period=3m` → verify delta and win rate

**Phase 6**: Trigger match confirmation → verify webhook fires with correct HMAC signature

---

## Non-Obvious Implementation Decisions

| Decision | Rationale |
|---|---|
| No ORM | Raw psycopg2 gives full SQL control for complex analytics queries and atomic batch operations. No abstraction layer between the well-defined DDL and the application. |
| No migrations | DDL is complete and stable. Run `sql/` files once on first deploy. DDL changes are infrequent and handled manually by running ALTER statements. |
| Nightly cron only (no 5-min polling) | For INTRA_ACADEMY events, confirmation deadline = end of match day. Auto-confirming at 23:58 is correct and sufficient. For INTER_ACADEMY events, ratings trigger is manual (event COMPLETED). No continuous polling needed — eliminates a Railway service entirely. |
| Gap > 500 evaluated at submission, not rating time | Eligibility is immutable once stored. ASI adjustment could theoretically change the effective gap later, but the spec uses raw ratings for this check. |
| Upset detection uses R_adj | Expected score is computed on ASI-adjusted ratings. The upset condition (winner's R_adj < loser's R_adj) must use the same adjusted values. |
| Diminishing signal → FRIENDLY, not ineligible | The match still counts toward rated_matches_completed and CR. Only K weight is reduced (FRIENDLY=0.5 vs LEAGUE=1.0). Allows the system to record the match while reducing its gaming potential. |
| Config TTLCache (60s) | system_configuration is read on every rating calculation in a batch. A 60s in-process cache avoids N DB reads per batch. Invalidated explicitly on `PATCH /config`. |
| `player_a_id < player_b_id` enforced at submission and query | Must be applied consistently everywhere: submission, diminishing signal check, dedup lookup, fixture slot creation. |
