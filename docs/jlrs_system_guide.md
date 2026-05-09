
## JLRS System Guide — Actors, Workflows, and Data Entry

---

This document explains how the system works end-to-end: who the actors are, what they do at each stage, and what data they need to enter across different scenarios.

---

## Actors

| Actor | Role in System | Typical Profile |
|------|--------------|----------------|
| **Admin** | League administrator. Full system access. Owns all setup, configuration, and dispute escalation | JLRS league coordinator or association official |
| **Coach** | Academy-level operator. Creates events, submits match results, manages their players | Academy head coach or designated staff |
| **Player** | Submits their own match results, confirms opponent-submitted results | Junior player (or parent on their behalf) |
| **Referee** | Neutral on-site official for INTER_ACADEMY events. Final authority on the day | Independent official assigned per event |
| **Umpire** | Table-level official. Scores and submits results at assigned table | Volunteer or academy staff assigned per table |

---

## Stage 1 — System Onboarding (One-time Setup)

### Admin does:

- Registers the league in JLRS (system bootstrap)  
- Sets global configuration parameters:
  - starting ratings  
  - K-factor thresholds  
  - tier boundaries  
  - match weights  
  - confirmation window  
  - inactivity thresholds  
- Creates user accounts for coaches, referees, and umpires  
- Registers each academy (name, city, state, minimum tables)  

---

### Coach does:

- Registers players in their academy — for each player:
  - Full name  
  - Date of birth  
  - Seeding level (`UNSEEDED`, `DISTRICT`, `STATE`, `NATIONAL`)  
  - If seeded: seeding reference (e.g., state ranking list reference)  
- Players start with appropriate rating and virtual matches based on seeding  

---

### Player does:

- Downloads the app and links account to player profile (optional)  
  - Coach can act on their behalf  

---

### Initial Rating Logic

- **Unseeded players**:
  - Start at rating = 1000  
  - 0 virtual matches  
  - Enter provisional phase (first 15 matches)  

- **Seeded players**:
  - District: 1200 (10 virtual matches)  
  - State: 1400 (20 virtual matches)  
  - National: 1500 (30 virtual matches)  
  - Skip provisional phase  

---

## Stage 2 — Season Setup (Each Season)

### Admin does:

- Creates new season (name, start date, end date)  
- Activates season  

---

### Coach does:

- Confirms enrolled players (registrations, transfers, deactivations)  
- Creates standing **INTRA_ACADEMY events** for daily training  
  - No end date — continuous through season  

---

### Academy Transfers

If a player moves academy:

- Coach/admin updates player's primary academy  
- System records transfer history  
- Future matches use new academy  
- Historical matches retain original academy snapshot  

---

## Stage 3A — Day-to-Day Intra-Academy Play  
(INTRA_ACADEMY + FRIENDLY)

Most frequent scenario — daily training sessions.

---

### Coach (before session):

- Optionally invokes fixture algorithm  
- Creates session under standing event  
- Marks players present  
- System generates pairings:
  - COMPETITIVE / STRETCH / ANCHOR  
  - Based on ratings + bootstrap phase  
- Publishes schedule  

---

### Coach or Player (during/after match):

- Submits result:
  - Opponent  
  - Sets score (e.g., 2–1)  
  - Retirement flag (if applicable)  
- Opponent (or coach) **confirms or disputes** before end of day (23:59:59)  

- If no action → **AUTO_CONFIRMED**

---

### System (end of day):

- Processes confirmed + auto-confirmed matches  
- Applies rating updates  
- Updates visible immediately  

---

### Notes

- No referee or umpire needed  
- Integrity ensured via:
  - Confirmation window  
  - Dispute mechanism  

---

## Stage 3B — Cross-Academy League Meet  
(INTER_ACADEMY + LEAGUE)

Typically monthly event with 2–4 academies.

---

### Admin / Coach (1–2 weeks before):

- Creates event  
- Defines:
  - Name  
  - Host academy  
  - Date  
- Adds participating academies  
- Assigns referee  

---

### Referee (after assignment):

- Assigns umpires per table  

---

### Coach (before event):

- Registers players  

---

### Event Day Flow

#### Check-in

- Coach/Player checks in players  
- Only CHECKED_IN players are eligible  

---

#### Pairing

- Referee runs fixture algorithm  
- System generates Swiss-style pairings across academies  
- Marks event IN_PROGRESS  

---

#### During Matches

**Umpire:**
- Submits results  

**Players:**
- Do not need to submit  

**Opponent:**
- Confirms or disputes  

---

#### Dispute Handling

- Referee reviews and resolves  
- Decision is final  

---

#### Event Completion

- Admin/Referee marks event COMPLETED  
- System checks:
  - No open disputes  
- Batch rating processing:
  - Chronological order  
  - Applies to all players  

---

### Key Rule

**Academy normalization** applied automatically for INTER_ACADEMY matches.

---

## Stage 3C — External Tournament  
(INTER_ACADEMY + TOURNAMENT_EXTERNAL)

JLRS records results but does not manage draw.

---

### Admin (before tournament):

- Registers event  
- Adds academies  
- Assigns referee (optional)  

---

### Coach/Admin (during):

- Registers + checks in players  
- Submits results per match or round  
- Opponent confirms  

---

### Post Tournament

- Event marked COMPLETED  
- Ratings applied in match timestamp order  

---

### Weighting

- Tournament matches receive **1.2× weight multiplier**

---

## Stage 3D — JLRS-Managed Tournament  
(INTER_ACADEMY + TOURNAMENT_MANAGED)

Fully managed by JLRS.

---

### Admin (before):

- Creates event with format:
  - SWISS  
  - TIER_BANDED_KNOCKOUT  
  - GROUP_THEN_KNOCKOUT  
- Adds academies  
- Assigns referee + umpires  

---

### Coach

- Registers + checks in players  

---

### Referee (event day):

- Runs draw:
  - Seeding by rating  
  - Tier grouping  
- Generates first-round pairings  
- Advances rounds:
  - Swiss → re-pair  
  - Knockout → advance winners  

---

### Umpire

- Submits match results  

---

### Referee

- Resolves disputes  
- Marks event COMPLETED  

---

## Stage 4 — Dispute Lifecycle

A dispute can be raised by:

- Opponent player  
- Opponent’s coach  

---

### How to raise

- From confirmation screen → select **Dispute**  

---

### Resolution

| Event Type | Resolver | Process |
|-----------|----------|--------|
| INTRA_ACADEMY + FRIENDLY | Admin | Review, correct, confirm, or void |
| INTER_ACADEMY + LEAGUE | Referee (primary) / Admin fallback | Final authority |
| INTER_ACADEMY + TOURNAMENT_EXTERNAL | Referee or Admin | Same |
| INTER_ACADEMY + TOURNAMENT_MANAGED | Referee (primary) | Same |

---

### Rules

- If not resolved within **72 hours** → match **AUTO-VOIDED**  
- If ratings already applied → rollback entries created  

---

## Stage 5 — Ongoing Monitoring and Reporting

### Rating Visibility Rules

| What | Who can see |
|------|------------|
| Current rating | All authenticated users |
| Rating history | All authenticated users |
| Full delta breakdown | Player + coaches + admins only |

---

### Coach Dashboard

- Ratings and tiers  
- Rating velocity  
- Match frequency  
- Age-group leaderboards  
- Fixture completion  

---

### Player View

- Own rating and tier  
- Full delta breakdown (own matches)  
- Other players’ ratings (no breakdown)  
- Upcoming fixtures  

---

### Public / Authenticated View

- All player ratings  
- Leaderboards  
- Match results (no breakdown)  

---

### Admin View

- Everything above  
- Full delta breakdown for all  
- ASI trends  
- Open disputes  
- Event status  
- Configuration history  

---

## Summary — Who Enters What, When

| Stage | Actor | Input |
|------|------|------|
| Onboarding | Admin | Academy + config + users |
| Onboarding | Coach | Player profiles |
| Season start | Admin | Season dates |
| Season start | Coach | Player enrollment |
| Event setup | Admin/Coach | Event + academies |
| Pre-event | Coach | Player registration |
| Event day | Coach/Referee | Check-in |
| Pairing | Coach/Referee | Run algorithm |
| Match | Player/Umpire | Match result |
| Post-match | Player/Coach | Confirm/dispute |
| Dispute | Referee/Admin | Resolve |
| Event close | Admin/Referee | Mark completed |

---

## Additional Actions

- Player transfer → Admin/Coach updates academy  
- Config change → Admin updates system parameters  

---


