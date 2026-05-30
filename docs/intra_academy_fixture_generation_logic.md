# Intra-Academy Session Fixture Generation and the Three-Phase Bootstrap Model

## Overview

For intra-academy sessions, fixture generation is a highly structured process designed to handle the evolution of a player pool from "flat" (unknown or initial ratings) to a matured, stable hierarchy. This evolution is managed through the Three-Phase Bootstrap algorithm.

When a coach generates fixtures for a session, the engine first analyzes the ratings of the players marked as present. It uses the rating distribution of the group to determine which fixture generation approach is most appropriate.

The Three-Phase Bootstrap is essentially the "brain" of the intra-academy engine. It ensures that the system does not try to force sophisticated tier-based pairing on a brand-new group of players where everyone's rating is still 1000. Instead, it provides a smooth path from discovery and information gathering to a highly structured competitive environment.

---

# Phase Detection: The Entry Gate to Fixture Generation

Before generating fixtures, the engine performs **Robust Phase Detection**.

Instead of simply looking at the difference between the highest-rated and lowest-rated player, the engine evaluates:

1. **Core Spread (P90 – P10)**
2. **The number of provisional players (players with low match confidence)**

This approach avoids **outlier hijacking**, where a single highly rated player in a room of beginners could incorrectly push the session into a mature pairing mode before the rest of the pool is ready.

---

## Core Spread (P90 – P10)

In statistics, the difference between the maximum and minimum values is highly sensitive to outliers. 

To solve this, the engine focuses on the bulk of the academy:

- **P90 (90th Percentile):** The rating below which 90% of players fall.
- **P10 (10th Percentile):** The rating below which 10% of players fall.

The engine calculates:

**Core Spread = P90 − P10**

By ignoring the top 10% and bottom 10% of players, the engine measures how separated the core player population really is.

### Why this matters

If the Core Spread is low (for example, under 100 points), it indicates that most players are still clustered together, regardless of one or two exceptional players.

In that situation, the engine keeps the session in the Discovery phase so ratings can continue to separate naturally.

---

## Provisional Majority Signal

The engine also considers rating confidence.

A player is considered provisional (rated_matches + virtual_matches < _threshold>) if they have not yet accumulated enough match history to establish a reliable rating.

The engine calculates the percentage of present players who are provisional.

According to configuration, if more than a threshold (for example, 60%) of the players are provisional, the system forces the session into the Discovery phase.

### Why this matters

Even if there is a large rating spread, if most players are new, those ratings are considered noisy and unreliable.

In this situation, it is safer to prioritize information gathering through broad exposure to opponents rather than relying on potentially inaccurate ratings for structured competitive pairing.

---

# Small Pools vs Large Pools

There is a specific threshold used to determine when to switch from a raw spread calculation to the Core Spread (P90–P10).

## Small Pools (< 10 Players)

The engine uses:

**Max Rating − Min Rating**

This is because, in very small groups, percentiles such as P90 and P10 are statistically unstable and do not effectively filter outliers.

## Large Pools (≥ 10 Players)

The engine uses:

**Core Spread = P90 − P10**

The 10-player threshold is currently hardcoded in the detect_phase method.

However, the percentile values used to calculate the Core Spread are configurable through FixtureConfig:

- core_spread_p_high
- core_spread_p_low

---

# The Three Bootstrap Phases

## Phase A: DISCOVERY (Bootstrap Phase A)

### When it is triggered

The Discovery phase is triggered when:

- The spread is less than or equal to 100 points, or
- The pool is mostly unseeded or majority provisional.

The spread may be either:

- Max Rating − Min Rating (small pools)
- Core Spread (P90 − P10) (large pools)

### Goal

The goal is information gain.

### Mechanism

The engine uses the Circle Method to generate a round-robin style schedule.

Players are treated as nodes in a circle and rotated so that everyone plays a variety of opponents.

### Outcome

This maximizes information gain for the system and helps ratings separate quickly.

---

## Phase B: TRANSITION (Bootstrap Phase B)

### When it is triggered

The Transition phase is triggered when:

- Spread is between 100 and 250 points, and
- The pool is no longer majority provisional.

### Important Clarification

The Core Spread logic is not exclusive to the STANDARD phase.

The Core Spread is used before phase selection occurs. It is the primary mechanism used to determine whether a session belongs in DISCOVERY, TRANSITION, or STANDARD.

Therefore, when a large pool is present, the Core Spread is equally relevant in determining the TRANSITION phase.

### Goal

This phase acts as the bridge between discovery and fully mature competitive pairing.

### Mechanism

The engine performs a Median Split, dividing players into:

- Upper Half
- Lower Half

### Competitive Rounds

Within each half, players are paired with their nearest neighbors to create close matches.

### Developmental Rounds

The halves are crossed (Upper vs Lower) to create stretch matches.

These matches allow lower-rated players to challenge players slightly above them.

---

## Phase C: STANDARD (Bootstrap Phase C)

### When it is triggered

Phase C is triggered when:

- The spread exceeds 250 points, and
- The session is not overridden into Discovery because of a majority of provisional players.

### Important Clarification

Phase C is not triggered solely because the spread exceeds 250 points.

The number of matches played and overall confidence level also play a critical role.

The engine first evaluates whether the session should be forced into Discovery because most players are still provisional.

Only if that condition is not met does it evaluate the rating spread.

Therefore, for Standard mode to be selected:

1. The spread must exceed 250 points.
2. The session must not have a majority of provisional players.

### Mechanism

In a matured academy, the engine uses Tier-Based Pairing.

Players are grouped into categories such as:

- Beginner
- Intermediate
- Advanced
- Elite

### Competitive Rounds

Players are paired with immediate rating neighbors:

- Rank 1 vs Rank 2
- Rank 3 vs Rank 4
- and so on.

### Stretch Rounds

The engine folds adjacent tiers together.

Examples:

- Top of Intermediate vs Bottom of Advanced

This creates developmental opportunities that are challenging but not out-of-band.

---

# Phase Determination Summary

After provisional-player checks have been completed and the appropriate spread has been calculated:

- Spread ≤ 100 → DISCOVERY
- 100 < Spread ≤ 250 → TRANSITION
- Spread > 250 → STANDARD

However, a provisional majority can override these spread rules and force the session into DISCOVERY.

[Present Player Pool] 
         │
         ▼
[Size-Based Spread Calculation] 
 ├── If N < 10:  Raw Spread (Max - Min)
 └── If N ≥ 10: Core Spread (P90 - P10)
         │
         ▼
[Provisional Majority Check]
 └── If Provisional Players > Threshold (e.g., 60%) ──┐
         │                                             │ (Override)
         ▼ (No Override)                               ▼
[Evaluate Final Spread]                         [Force DISCOVERY Phase]
 ├── Spread ≤ 100  --> DISCOVERY                       │
 ├── 100 < Spread ≤ 250 --> TRANSITION                 │
 └── Spread > 250  --> STANDARD                        │
         │                                             │
         └───────────────────►   ◄─────────────────────┘
                             │
                             ▼
                 [Execute Phase Matcher]

---

# Pairing Solver and Operational Constraints

## One Match Per Player

A player cannot be scheduled more than once in the same wave or round.

## Session Capacity

The engine calculates the expected number of matches per player using:

- Number of tables
- Session duration

## Rematch Policy

The engine consults recent match history supplied by the service layer.

This helps avoid pairing players who faced each other in the previous session.

---

# Semantic Fixture Output

## Round Intent

- COMPETITIVE (fairness focused)
- DEVELOPMENTAL (growth focused)

## Gap Band

Examples include:

- STRETCH (for moderate developmental gaps)
- OUT_OF_BAND (for extreme outliers)

## Player Roles

- PEER – playing someone of similar level
- STRETCHING – playing up
- ANCHORING – playing down

---

# Inter-Academy (League) Events

Inter-academy events use a different approach from intra-academy sessions.

The Core Spread (P90–P10) and the Three-Phase Bootstrap logic are not used to determine the pairing strategy.

## Strategy-Driven, Not Phase-Driven

League fixtures are determined by the strategy selected by the coach, such as:

- TIER_MATCHED
- TEAM_FORMAT

## Rating Spread Usage

The inter-academy dispatcher calls a helper function rating_spread(), which always performs:

**Max Rating − Min Rating**

This spread is used primarily for metadata and reporting purposes rather than driving pairing decisions.

## Rating Maturity

Rating maturity does not determine the pairing strategy in inter-academy events.

Because inter-academy events often involve players from different ecosystems, the engine assumes ratings are mature enough to be compared or uses strategies such as TEAM_FORMAT that rely on ranking rather than absolute rating gaps.

As a result:

- Core Spread (P90–P10) is not always used for inter-academy events.
- The Three-Phase Bootstrap model is not used for inter-academy events.
- Pairing is strategy-driven rather than phase-driven.

---

# Summary

The fixture engine uses a robust phase-detection mechanism based on:

- Rating spread (Max-Min for small pools, Core Spread for large pools)
- Provisional-player majority

to determine whether the academy is in:

1. DISCOVERY – maximizing information gain through round-robin style exposure.
2. TRANSITION – balancing competitive and developmental pairings.
3. STANDARD – using tier-based pairing in a mature rating ecosystem.

For large pools, the Core Spread (P90–P10) is used before phase selection occurs and therefore influences DISCOVERY, TRANSITION, and STANDARD phase determination.

A session enters STANDARD mode only when the rating spread indicates a mature hierarchy and the player pool has sufficient rating confidence. This prevents unreliable ratings or isolated outliers from prematurely pushing the academy into highly structured pairing modes.

Inter-academy events operate differently. They do not use the Three-Phase Bootstrap model or Core Spread-based phase detection. Instead, fixture generation is driven by the competition strategy selected by the coach.
