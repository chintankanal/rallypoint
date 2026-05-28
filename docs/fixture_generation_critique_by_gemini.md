# Technical Review & Refactoring Guide: Table Tennis Fixture Engine

This document provides an exhaustive architectural critique and refactoring blueprint for the pure-Python table tennis tournament fixture generation engine. It addresses core issues spanning **Correctness**, **Fairness**, **Accuracy**, **Practicality**, and **Algorithm Quality**, offering concrete algorithmic solutions and production-grade code modifications for each.

---

## 1. Practicality & System Architecture: The Resource-Time Capacity Mismatch

### Problem Highlight
The engine determines maximum rounds using `calculate_session_capacity()`. However, the individual sub-strategy generation functions (e.g., `_tier_matched`) build fixtures based on combinatorics (such as completing an entire Round Robin cycle for a tier), completely ignoring the time limit boundaries. 

If a venue booking only allows **2 rounds**, but a 12-player tier requires **11 rounds** to complete a single competitive cycle, the engine silently generates all 11 rounds. This creates a severe logistical failure when the tournament director is handed an unplayable schedule sheet.

Furthermore, blindly truncating an 11-round cycle to 2 rounds ruins the mathematical integrity of the tournament standings, because match difficulties become completely unbalanced.

### Recommended Approach
Implement an **Advisory Layer** as a gatekeeper before match generation occurs. The system should calculate whether the tournament design is feasible within the given limits. If a resource mismatch is caught, it stops execution and returns explicit, actionable feedback to the organizer on how many tables or hours they need to add.

### Implementation Blueprint

```python
import math

_MATCH_DURATION = {"BEST_OF_3": 20, "BEST_OF_5": 30, "BEST_OF_7": 40}
_CHANGEOVER = 5

def validate_tournament_feasibility(
    num_players: int,
    num_tables: int,
    session_minutes: int,
    match_format: str,
    strategy: str,
    players_by_id: dict,
    tier_assignments: dict = None
) -> dict:
    """
    Analyzes physical resource, time constraints, and format structural limits.
    Returns explicit advice if the requested session parameters are unfeasible.
    """
    duration = _MATCH_DURATION.get(match_format.upper(), 20)
    slot_time = duration + _CHANGEOVER
    matches_per_table = math.floor(session_minutes / slot_time)
    
    # Calculate mathematically required rounds for a fair outcome
    if strategy in ("TIER_MATCHED", "FULL_ROUND_ROBIN"):
        rounds_required = num_players if num_players % 2 == 1 else (num_players - 1)
    else:
        rounds_required = 4  # Fallback threshold for hybrid systems

    pairs_per_round = num_players // 2
    total_slots_available = matches_per_table * num_tables
    rounds_possible = math.floor(total_slots_available / pairs_per_round) if pairs_per_round > 0 else 0

    warnings = []
    is_feasible = rounds_possible >= rounds_required

    # 1. INTERCEPT: Fairness & Format Advisory Validations
    if strategy == "CROSS_ACADEMY_ONLY":
        # Check if a single academy dominates > 50% of the field
        academy_counts = {}
        for p in players_by_id.values():
            ac_id = p["academy_id"]
            academy_counts[ac_id] = academy_counts.get(ac_id, 0) + 1
        
        for ac_id, count in academy_counts.items():
            if count > (num_players / 2):
                warnings.append(
                    f"FORMAT WARNING: Academy '{ac_id}' accounts for {round((count/num_players)*100)}% of the field. "
                    "A strict Cross-Academy format will force heavy teammate sit-out periods or broken pairs."
                )

    if strategy == "TIER_MATCHED" and tier_assignments:
        tier_analysis = validate_tier_distribution(tier_assignments, num_tables)
        warnings.extend(tier_analysis["warnings"])
        if not tier_analysis["viable"]:
            is_feasible = False

    # Calculate exact compensation metrics for the organizer
    total_time_needed = rounds_required * slot_time
    extra_minutes_needed = max(0, total_time_needed - session_minutes)
    extra_hours = round(extra_minutes_needed / 60, 1)

    total_matches_needed = rounds_required * pairs_per_round
    if matches_per_table > 0:
        tables_needed = math.ceil(total_matches_needed / matches_per_table)
        extra_tables = max(0, tables_needed - num_tables)
    else:
        tables_needed = 0
        extra_tables = 0

    return {
        "feasible": is_feasible,
        "rounds_required": rounds_required,
        "rounds_possible": rounds_possible,
        "warnings": warnings,
        "advice": {
            "increase_time_by_hours": extra_hours,
            "total_time_required_minutes": total_time_needed,
            "increase_tables_by": extra_tables,
            "total_tables_required": tables_needed
        },
        "error_message": (
            f"CRITICAL CONSTRAINT MISMATCH: A fair {strategy} schedule requires {rounds_required} rounds, "
            f"but your constraints only allow for {rounds_possible} rounds."
        ) if not is_feasible else ""
    }

```

---

## 2. Correctness: Sub-Round Concurrency / Double-Booking Bug

### Problem Highlight

In `_assign_tables()`, when the number of concurrent player pairs exceeds the number of physical tables (`len(pairs) > num_tables`), the code splits matches into sub-rounds `"A"` and `"B"` using a static modulo index step:

```python
sub = ("A" if i < num_tables else "B") if needs_subrounds else None
table = (i % num_tables) + 1

```

If a player is positioned in the input list such that they appear in both pair index `0` and pair index `num_tables + 1`, the code assigns them to Sub-Round A on Table 1, and simultaneously to Sub-Round B on Table 2. Because sub-rounds represent back-to-back matches within the same round window, this creates an impossible double-booking.

### Recommended Approach

Track player assignments dynamically while iterating through the pairs list. If a player is already assigned a match in Sub-Round A, their next match must be forced into Sub-Round B, regardless of its original index placement.

### Implementation Blueprint

```python
def _canonical(pid_a: str, pid_b: str) -> tuple[str, str]:
    return (pid_a, pid_b) if pid_a < pid_b else (pid_b, pid_a)

def _assign_tables(
    pairs: list[tuple],
    num_tables: int,
    round_number: int,
    match_category: str,
    players_by_id: dict,
    max_rounds: int,
    strategy: str = "TIER_MATCHED",
) -> list[dict]:
    """
    Safely assigns player pairs to tables. Prevents scheduling past capacity limits
    and uses real-time player tracking to eliminate sub-round concurrency bugs.
    """
    if round_number > max_rounds:
        return []

    slots = []
    if not pairs:
        return slots

    needs_subrounds = len(pairs) > num_tables
    sub_round_a_players = set()  # Tracks who is physically on a table in block A

    for i, (pid_a, pid_b) in enumerate(pairs):
        table = (i % num_tables) + 1

        # Handle BYE allocations safely
        if pid_a is None or pid_b is None:
            active_id = pid_a if pid_a is not None else pid_b
            if needs_subrounds:
                sub = "B" if active_id in sub_round_a_players else ("A" if i < num_tables else "B")
            else:
                sub = None
            
            if sub == "A" and active_id:
                sub_round_a_players.add(active_id)

            slots.append({
                "round_number": round_number,
                "sub_round": sub,
                "table_number": table,
                "match_category": "COMPETITIVE",
                "player_a_id": active_id,
                "player_b_id": None,
                "expected_rating_gap": 0.0,
                "fixture_strategy": strategy,
            })
            continue

        canon_a, canon_b = _canonical(pid_a, pid_b)
        gap = abs(float(players_by_id[canon_a]["current_rating"]) - float(players_by_id[canon_b]["current_rating"]))

        # Concurrency Safeguard: If a player is locked in sub-round A, shift the match to B
        if needs_subrounds:
            if canon_a in sub_round_a_players or canon_b in sub_round_a_players:
                sub = "B"
            else:
                sub = "A" if i < num_tables else "B"
        else:
            sub = None

        if sub == "A":
            sub_round_a_players.add(canon_a)
            sub_round_a_players.add(canon_b)

        slots.append({
            "round_number": round_number,
            "sub_round": sub,
            "table_number": table,
            "match_category": match_category,
            "player_a_id": canon_a,
            "player_b_id": canon_b,
            "expected_rating_gap": round(gap, 2),
            "fixture_strategy": strategy,
        })
    return slots

```

---

## 3. Accuracy: Broken Round Robin Circle Method in Transition Phase

### Problem Highlight

In `generate_transition_fixtures`, the embedded function `within_half_pairs` claims to execute adjacent pairings within split halves via an index shift. However, its tracking mechanism simply slides a window across adjacent array entries:

```python
a, b = pids[idx], pids[(idx + 1) % len(pids)]

```

This is not a mathematically correct round-robin circle rotation. For a 4-player pool, this window logic schedules Player 2 to play against both Player 1 and Player 3 in the exact same round block, while skipping other mandatory pairings. This corrupts the round-robin structure and causes dead ends.

### Recommended Approach

Replace the array sliding-window logic with a proper implementation of the Circle Method. Pin the first player in the slice ($P_0$) and shift the remaining elements systematically around the pivot to ensure balanced pairings.

### Implementation Blueprint

```python
def within_half_pairs_accurate(half_players: list[dict], round_idx: int) -> list[tuple]:
    """
    Executes a mathematically sound Circle Method round-robin rotation 
    within an isolated subset (half) of players.
    """
    n = len(half_players)
    if n < 2:
        return [(half_players[0]["player_id"], None)] if n == 1 else []

    ps = list(half_players)
    if n % 2 == 1:
        ps.append(None)  # Inject BYE sentinel to ensure an even pool size

    num_elements = len(ps)
    fixed = ps[0]
    rotating = list(ps[1:])
    
    # Rotate elements around the fixed pivot point
    r = round_idx % (num_elements - 1)
    rotating = rotating[-r:] + rotating[:-r] if r else rotating

    raw_pairs = [(fixed, rotating[-1])]
    mid = (num_elements - 2) // 2
    for i in range(mid):
        raw_pairs.append((rotating[i], rotating[-2 - i]))

    return [
        (
            a["player_id"] if a is not None else None,
            b["player_id"] if b is not None else None,
        )
        for a, b in raw_pairs
    ]

```

---

## 4. Fairness: "Sit-out" Spikes, Team Format, & Tier Bottlenecks

### Problem Highlights

* **Issue A (`_cross_academy_only` Teammate Spikes):** If the circle method pairs two players from the same academy, the engine immediately gives both players an individual round BYE. If a dominant academy brings 75% of the total players, its participants get stuck in consecutive rounds of sitting out, killing tournament engagement.
* **Issue B (`_team_format` Lineup Bottlenecks):** Matches are made strictly by rank index matching (`pos`). If Academy A brings 8 players and Academy B brings 2 players, positions 3 through 8 for Academy A instantly receive a non-playing BYE slot for that round block.
* **Issue C (`_tier_matched` Odd-Number Islands):** When parsing players into separate rating tiers, any tier left with an odd number of players (e.g., an Elite Tier of 5) becomes an isolated ecosystem. Because an odd group cannot pair up perfectly, **one player in that tier is mathematically forced to take a BYE every single round**, leaving them stranded even if tables are empty elsewhere.
* **Issue D (`_tier_matched` Infrastructure Starvation):** If Tier 1 has 12 players (demanding 6 concurrent tables) and Tier 2 has 4 players (demanding 2 concurrent tables), running this round concurrently requires 8 tables. If the venue only has 4 tables, Tier 1 overloads the capacity pool. Sub-rounds will generate heavy backlogs, drastically increasing downtime for the isolated players in smaller tiers.

### Recommended Approach (The Unified Advisory Gatekeeper)

Instead of relying on downstream logic to make poor formatting trade-offs (like generating endless BYEs or forcing teammate structural clashes), **integrate player distribution checks into the front-end Advisory Layer.** By evaluating group counts, academy ratios, and roster balances *before* match generation begins, the advisor can flag structural user-experience issues immediately:

1. **Academy Distribution Ratio:** Intercept execution if a single academy makes up $>50\%$ of a `CROSS_ACADEMY_ONLY` pool, recommending a tier-matched fallback instead.
2. **Lineup Balance Index:** Flag uneven team rosters early, allowing the engine to route excess players into an internal competitive validation pool.
3. **Sub-Pool Parity Check:** Identify odd-numbered tier partitions, prompting the coordinator to shift a borderline ranking player up or down to eliminate guaranteed rotational BYEs.

### Implementation Blueprint: Live Swap & Tier Multi-Constraint Validations

```python
def _clean_cross_academy_pairs(raw_pairs: list[tuple], players_by_id: dict) -> list[tuple]:
    """
    Looks ahead to find cross-academy pairs and swaps partners when teammate 
    clashes occur, avoiding unnecessary consecutive BYEs.
    """
    pairs = list(raw_pairs)
    
    for i in range(len(pairs)):
        a, b = pairs[i]
        if a is None or b is None:
            continue
            
        if players_by_id[a]["academy_id"] == players_by_id[b]["academy_id"]:
            # Conflict caught: Look down the stack for a safe cross-academy swap partner
            for j in range(i + 1, len(pairs)):
                c, d = pairs[j]
                if c is None or d is None:
                    continue
                
                # Verify that swapping elements yields valid inter-academy matches
                if (players_by_id[a]["academy_id"] != players_by_id[d]["academy_id"] and 
                    players_by_id[c]["academy_id"] != players_by_id[b]["academy_id"]):
                    
                    pairs[i] = (a, d)
                    pairs[j] = (c, b)
                    break
    return pairs

def validate_tier_distribution(tier_assignments: dict[str, list], num_tables: int) -> dict:
    """
    Analyzes tier sub-pools to catch Odd-Number Islands and Table Choke Points 
    before fixture generation begins.
    """
    warnings = []
    critical_choke = False
    max_concurrent_tables_needed = 0
    
    for tier_name, players in tier_assignments.items():
        n = len(players)
        if n == 0:
            continue
            
        # Catch the Odd-Number Island Flaw
        if n % 2 != 0:
            warnings.append(
                f"TIER MISMATCH: Tier '{tier_name}' has an odd number of players ({n}). "
                "One player will be forced to take a BYE every single round within this pool."
            )
            
        max_concurrent_tables_needed += (n // 2)

    # Catch the Single-Table Choke Point Flaw
    if max_concurrent_tables_needed > num_tables:
        warnings.append(
            f"CAPACITY WARNING: Running all tiers concurrently demands {max_concurrent_tables_needed} tables, "
            f"but your venue configuration only provides {num_tables}. Matches will be split into sub-rounds."
        )
        if max_concurrent_tables_needed > (num_tables * 2):
            critical_choke = True  # Too choked to guarantee structural integrity cleanly

    return {
        "viable": not critical_choke,
        "warnings": warnings,
        "total_tables_demanded": max_concurrent_tables_needed
    }

```

---

## 5. Algorithmic Quality & Cleanliness

### A. Hidden State Leaks in Deduplication Loop

In `generate_standard_fixtures`, the loop captures *all* matches generated in the previous round and adds them to `session_pairs`. This includes fallback matches where players from adjacent tiers were paired out of necessity.

By treating these fallback matches as intentional pairings, the engine locks those players out of playing their highly optimized, intended matches in later rounds.

**Solution:** Only add matches to `session_pairs` if their calculated gap falls strictly within the true structural strategy categories (e.g., matching the category rules of that round).

### B. Greedy Range Scan Risks ($O(N^2)$ Dead Ends)

In `stretch_pairs`, the code scans a descending-sorted player list to find stretch partners using a strict threshold ($100 < \Delta \le 250$). If a top-tier player has an outlier rating, scanning down the array *increases* the rating gap. The loop keeps searching in the wrong direction, wastes computation time, and ends up failing to find a partner.

**Solution:** Short-circuit the loop the moment the rating gap exceeds the maximum threshold (`_STRETCH_MAX`). Since the array is pre-sorted, gaps will only grow larger from that point on.

### C. Violation of Pure Testability Functional Constraints

The inline imports of `from app.utils.rating_math import get_tier, _load_config` break the core promise of a zero-I/O, fully mockable test suite. If `_load_config()` reads a file or accesses an external service, it creates external dependencies.

**Solution:** Use **Dependency Injection**. Pass the configuration dictionaries and the tier evaluation logic directly into `generate_fixtures` as clean arguments.

---

## 6. Structural Critique of Rating Spreads (Phases & Tiers)

```
  TYPICAL TABLE TENNIS RATING SCALE
  [0-800]        [800-1400]       [1400-2000]       [2000-2600+]
  Beginner      Intermediate       Advanced           Elite/Pro
  (Volatile)    (Gaps Matter)    (Gaps Narrow)     (Gaps Critical)

```

The hardcoded boundaries (`_COMPETITIVE_MAX = 100`, `_STRETCH_MAX = 250`) are fragile when used across a real academy setup due to how rating differentials scale across skill levels.

### The Scaling Flaw

* **At the Elite Tier (2000 - 2600+):** A 100-point difference represents a massive gap in skill. A 2400-rated pro will consistently dominate a 2300-rated challenger. Labeling this as "COMPETITIVE" is inaccurate.
* **At the Grassroots Tier (0 - 800):** A 100-point gap is minimal due to high rating volatility in developing players. Matches between players with larger gaps here are often highly competitive, but the system incorrectly categorizes them as "STRETCH" fixtures.

### Whole-Pool Phase Flaw

The global `detect_phase` relies entirely on a raw spread check: `spread = max(ratings) - min(ratings)`. If a session contains twenty 1200-rated intermediate players and **one** 1600-rated elite coach or advanced junior enters the room, the spread instantly widens past 250.

This single outlier shifts the entire engine's phase to `STANDARD` for everyone, replacing the balanced round-robin structure the intermediate players needed with a folded stretch format.

### Resolution: Dynamic Percentage-Based Threshold System

Replace the static integers with a dynamic, percentage-based threshold system that scales based on the average rating of the active pool.

```python
def get_dynamic_thresholds(avg_rating: float) -> tuple[float, float]:
    """
    Dynamically scales maximum allowable competitive rating gaps 
    based on the absolute skill level of the active pool.
    """
    if avg_rating < 1000:
        return 150.0, 300.0  # Wider gaps allowed for volatile grassroots players
    if avg_rating > 2000:
        return 50.0, 150.0   # Narrower gaps enforced for elite/pro fields
    return 100.0, 250.0      # Standard defaults for intermediate players

```

```
***

```