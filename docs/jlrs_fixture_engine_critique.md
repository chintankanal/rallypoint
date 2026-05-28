# JLRS Fixture Engine Critique

## Scope

This review compares:

- `docs/jlrs_fixtures_design`
- `app/services/fixture_engine.py`
- `app/utils/rating_math.py`
- selected tests in `tests/unit/test_fixture_engine.py`

The focus is intra-academy and inter-academy fixture generation for table tennis, judged on quality, practicality, correctness, fairness, completeness, and accuracy. I also include a structural critique of the current rating-spread / phase / tier model.

## Executive Summary

The overall intent is strong:

- bootstrap from flat ratings without coach seeding
- keep most matches close
- deliberately include developmental stretch matches
- support several inter-academy formats

But the current implementation has multiple issues that make it unsafe to rely on as the final scheduling engine:

1. The transition-phase algorithm is invalid and can schedule the same player twice in one round.
2. The match-category model is internally inconsistent: the design defines `COMPETITIVE`, `STRETCH`, and `ANCHOR`, but the engine only emits `COMPETITIVE` and `STRETCH`, and it can label 0-gap and 400-gap matches as `STRETCH`.
3. The standard phase can generate extreme cross-tier leftovers that violate the stated stretch limits and fairness goals.
4. The phase and tier structure is too brittle because it uses raw session `max - min` spread instead of a robust measure of pool shape and density.
5. The inter-academy strategies do not consistently do what the design says they do, especially `TIER_MATCHED` and `CROSS_ACADEMY_ONLY`.
6. The inter-academy generators are not session-ready schedules; they ignore tables, duration, and sub-round capacity entirely.

The result is a design that is conceptually promising but not yet operationally reliable.

## What Is Good

- Discovery phase using the circle method is a sensible bootstrap choice for flat ratings. See `fixture_engine.py:168-225`.
- Separating intra-academy and inter-academy generation is the right architectural direction.
- The standard-phase intent to mix close matches and developmental matches is valuable.
- The design document is ambitious and explains the purpose of the system clearly, even though several claims are not matched by the code.

## Critical Findings

### 1. Transition phase is not a valid round scheduler

Relevant code:

- `fixture_engine.py:230-298`
- especially `within_half_pairs()` at `250-270`

The transition algorithm can schedule one player in multiple matches in the same round.

Why it happens:

- `within_half_pairs()` walks adjacent windows across the half.
- It records unique pairs, but it does not enforce the more important constraint: each player must appear at most once per round.

For a half `[p1, p2, p3, p4]`, it generates:

- `(p1, p2)`
- `(p2, p3)`
- `(p3, p4)`

That is not a legal round; `p2` and `p3` each appear twice.

Reproduced example with 8 players:

```text
Round 1 pairs:
(p1,p2) (p2,p3) (p3,p4) (p5,p6) (p6,p7) (p7,p8)
Duplicate players in same round:
p2, p3, p6, p7
```

With an odd total player count, the transition stretch round is also incomplete.

Relevant code:

- `cross_pairs()` at `272-278`

It pairs `min(len(lower), len(upper))` players and does not issue a BYE or fallback for the extra player in the larger half.

Reproduced example with 7 players:

```text
Round 2 pairs:
(p3,p4) (p2,p5) (p1,p6)
Missing player:
p7
```

This is a correctness failure, not just a quality concern.

### 2. Match categories do not match the design

Relevant design:

- `jlrs_fixtures_design:22-32`
- `jlrs_fixtures_design:402-425`

Relevant code:

- `fixture_engine.py:101-104`
- `fixture_engine.py:145-163`
- `fixture_engine.py:643-653`

Problems:

- The design defines three categories: `COMPETITIVE`, `STRETCH`, `ANCHOR`.
- The engine never emits `ANCHOR`.
- `_category()` returns `STRETCH` for every gap above 100, with no upper bound.

So:

- a 110-point match and a 400-point match both become `STRETCH`
- the system cannot distinguish “stretching up” from “anchoring down”
- any downstream analytics that depend on anchor behavior cannot be correct

This gets worse in the standard-phase stretch round:

- `_assign_tables()` only recomputes category from actual gap when the round intent is `"COMPETITIVE"` (`150-152`)
- when the round intent is `"STRETCH"`, it preserves the label even if the actual gap is 0 or 400

Reproduced example with ratings `[1600, 1200, 1200, 1200]` in standard phase:

```text
Round 1:
(p2,p3) COMPETITIVE gap 0
(p1,p4) STRETCH gap 400

Round 3:
(p1,p2) STRETCH gap 400
(p3,p4) STRETCH gap 0
```

That breaks correctness, fairness, analytics, and trust in the labels.

### 3. Standard phase can force extreme leftover pairings

Relevant code:

- `fixture_engine.py:342-387`
- especially leftover handling at `380-385`

The design says competitive rounds should mostly be peer-level and leftover odd players should be paired to the closest adjacent-tier player. But the actual implementation simply collects leftovers from each tier and pairs them in order.

That means a singleton top tier can be paired against the last leftover of the next tier even when the gap is far outside the intended competitive or stretch band.

Reproduced example:

- ratings: `[1600, 1200, 1200, 1200]`
- tiers: `NATIONAL_TRACK x1`, `ADVANCED x3`

Round 1 becomes:

- `1200 vs 1200`
- `1600 vs 1200` with a 400-point gap

That is a direct violation of the design claim that stretch matches should stay within 100-250 and that no match should feel uncompetitive.

### 4. The phase gate is structurally brittle

Relevant code:

- `fixture_engine.py:33-47`

Relevant design:

- `jlrs_fixtures_design:227-242`

The phase decision is based only on:

```text
spread = max(rating) - min(rating)
```

That is too fragile for real attendance.

Example:

- 20 players around 1200
- 1 visiting player at 1600

Observed result:

```text
phase = STANDARD
spread = 400
```

Even though the core pool is basically homogeneous, the single outlier forces the whole session into the most structured tier-based mode.

This creates several structural problems:

- one outlier can flip the whole session
- the phase can oscillate from day to day depending on attendance
- `STANDARD` can trigger even when there is not enough density inside tiers to support it
- the gate ignores provisional confidence, cluster shape, and tier occupancy

This is the biggest design-level issue in the file.

### 5. The code violates its own “zero DB access” contract

Relevant code:

- module docstring at `fixture_engine.py:1-17`
- imports and config loads at `fixture_engine.py:316-318` and `724-726`
- config loader at `rating_math.py:38-61`

The fixture engine claims:

```text
pure Python, zero DB access, fully unit-testable
```

But `generate_standard_fixtures()` and `_tier_matched()` call `_load_config()`, which can hit the database on cache miss.

This is a quality and architecture issue:

- the engine is not actually pure
- tests may pass by fallback or cache behavior instead of by explicit dependency control
- fixture behavior can change with DB config without the generator interface showing it

## Major Design / Accuracy Mismatches

### 6. The design document and implementation disagree on key rules

Examples:

- Phase A trigger:
  - doc says “<= 100” at `jlrs_fixtures_design:146-149`
  - code uses `< 100` at `fixture_engine.py:43-44`

- Phase C trigger:
  - doc says “> 250” at `jlrs_fixtures_design:219-223`
  - code uses `>= 250` at `fixture_engine.py:45-47`

- Fewer than 6 players:
  - doc says pure round-robin at `jlrs_fixtures_design:340-348`
  - code still uses spread-based phase detection

- Discovery ordering:
  - doc says deterministic non-rating order at `jlrs_fixtures_design:152-156`
  - code uses incoming list order without normalizing it at `fixture_engine.py:173`

- Deduplication:
  - doc says skip pairs that already played 2 rated matches in 7 days at `jlrs_fixtures_design:285`
  - code only accepts a flat `recent_match_pairs` set, and only uses it for standard stretch rounds and inter-academy novelty swaps

- Cross-academy monthly meets:
  - doc describes a 3-round Swiss-like meet at `jlrs_fixtures_design:614-624`
  - implementation contains no Swiss logic at all

This matters because users, coaches, and future developers will think the engine does something that it does not actually do.

### 7. Tiers and competitive/stretch bands are not aligned

Relevant tier config:

- `rating_math.py:70-87`

Default tier bands are 200-point wide:

- Beginner: `<= 899`
- Intermediate: `900-1099`
- Advanced: `1100-1299`
- Elite: `1300-1499`

But the engine’s competitive threshold is 100 points:

- `_COMPETITIVE_MAX = 100` at `fixture_engine.py:27`

So “same tier” does not imply “competitive.”

Concrete example:

- `1099` vs `900` are both `INTERMEDIATE`
- gap = `199`
- that match is same-tier but not competitive by the engine’s own category rule

Reproduced `TIER_MATCHED` example:

```text
a1 = 1099
b1 = 900
Result: TIER_MATCHED produces one STRETCH match with gap 199
```

That undermines several statements in the design:

- “tier-matched” does not reliably mean peer-level
- “same tier” is too coarse to serve as the main fairness unit

### 8. Tier-specific stretch limits in the document are not implemented

Relevant design:

- `jlrs_fixtures_design:402-425`

The document gives tier-specific limits, e.g.:

- Beginner stretch up: max 200
- Elite stretch up: max 200
- Intermediate / Advanced: max 250

The code does not implement any of that.

It uses one global hardcoded rule:

- competitive if `gap <= 100`
- stretch otherwise

There is no:

- tier-specific max stretch
- invalid-gap classification
- protection for elite/national-track players from 240-250 point stretches

This is an accuracy gap between design and implementation.

## Practicality and Scheduling Gaps

### 9. Sub-round support only works for two waves

Relevant code:

- `fixture_engine.py:125-148`

If a round has more pairs than tables, the engine only labels:

- `A` for the first `num_tables`
- `B` for everything else

That fails whenever more than two waves are needed.

Reproduced example:

- 20 players
- 2 tables
- 1 round requires 10 matches

Observed sub-round labels:

```text
(A,1) (A,2) (B,1) (B,2) (B,1) (B,2) (B,1) (B,2) (B,1) (B,2)
```

This is not executable because there are really five waves, not two.

### 10. `matches_per_player` is only a reporting estimate, not a schedule guarantee

Relevant code:

- `fixture_engine.py:59-85`
- `fixture_engine.py:544-548`

The engine returns `matches_per_player`, but the actual slots can deviate because:

- odd player counts create rotating BYEs
- inter-academy strategies create many BYEs
- transition phase can omit a player entirely in a stretch round
- league generators do not use session-capacity constraints

That makes the field potentially misleading to operators and UI.

### 11. `round_offset` is ignored outside discovery

Relevant code:

- `fixture_engine.py:537-542`

`generate_fixtures()` accepts `round_offset`, but only discovery uses it.

Transition and standard always restart round numbers at 1.

Reproduced example:

- call `generate_fixtures(..., round_offset=5, ...)` in standard phase
- observed rounds returned: `1,2,3,4`

That is a correctness issue for multi-session continuity.

### 12. Competitive-round rematch control is mostly missing

Relevant design:

- `jlrs_fixtures_design:285`

Relevant code:

- `fixture_engine.py:396-405`
- `fixture_engine.py:497-500`

The design talks about skipping pairs that already played multiple recent matches. In practice:

- discovery ignores recent-match history
- transition ignores recent-match history
- standard competitive rounds ignore recent-match history
- standard stretch uses only a set, not a count window
- inter-academy uses a one-pass novelty swap, not a true rematch constraint

This weakens both fairness and practical usefulness.

## Inter-Academy Findings

### 13. `TIER_MATCHED` does not actually enforce cross-academy pairing

Relevant design:

- `jlrs_fixtures_design:487-507`

Relevant code:

- `fixture_engine.py:717-764`

The design says:

- if 2+ academies are present in a tier, use cross-academy round-robin and skip intra-academy pairs

The code does not do that.

It:

1. interleaves players by academy
2. runs a normal round-robin inside the tier

That still produces intra-academy matches.

Reproduced example with one tier containing:

- Academy A: `a1`, `a2`
- Academy B: `b1`, `b2`
- Academy C: `c1`

Observed rounds include:

```text
Round 1: (b1,b2)
Round 3: (a1,a2)
```

So the implementation contradicts the stated strategy.

### 14. `TIER_MATCHED` silently drops singleton tiers

Relevant code:

- `fixture_engine.py:745-747`

If a tier has only one player, the code just skips it:

```python
if len(all_in_tier) < 2:
    continue
```

That player receives no BYE, no fallback, and no visibility in the output.

Reproduced example:

- `a1 = 1510` in `NATIONAL_TRACK`
- `a2 = 1090`, `b1 = 1080` in `INTERMEDIATE`

Observed result:

- only `a2 vs b1` is scheduled
- `a1` disappears completely

This is a completeness and fairness failure.

### 15. `CROSS_ACADEMY_ONLY` can generate same-academy matches after novelty swap

Relevant code:

- `_swap_for_novelty()` at `fixture_engine.py:588-619`
- used by `CROSS_ACADEMY_ONLY` at `803`

The swap heuristic only minimizes rematches. It does not preserve academy constraints.

End-to-end reproduced case:

- played pair history contains `('a1','b2')`
- `CROSS_ACADEMY_ONLY` produces in round 2:

```text
(a1,c1)
(b1,b2)
```

So the strategy named “cross academy only” can output an intra-academy match.

This is a very important correctness bug because it breaks the strategy’s core contract.

### 16. `cross_academy_pct` can look good while the schedule is practically poor

Relevant code:

- `fixture_engine.py:815`

Example:

- academy sizes `4 vs 1`
- strategy `CROSS_ACADEMY_ONLY`

Observed behavior:

- `cross_academy_pct = 100.0`
- but most slots are BYEs
- one full round has zero real matches

So the metric overstates usefulness because it ignores match volume and player participation balance.

### 17. Inter-academy generators are not session schedulers

Relevant code:

- `fixture_engine.py:622-654`

The intra-academy generator considers:

- session minutes
- tables
- sub-rounds

The inter-academy generator does not.

`_assign_tables_league()` simply numbers matches `1..N` inside the round and explicitly says physical scheduling is out of scope.

That means the output is a pairing matrix, not an executable event plan.

This is okay only if the product intentionally separates:

- pairing generation
- court/table scheduling

Right now the design document mixes both concerns, so the result feels more complete than it really is.

### 18. `TEAM_FORMAT` is coherent, but the document overstates its scaling simplicity

Relevant design:

- `jlrs_fixtures_design:561-610`

The strategy itself is understandable and useful if the goal is team-versus-team scoring.

But the document says:

```text
10 academies x 4 players = 40 matches in 45 rounds
```

That is not correct.

With 10 academies:

- academy pairings = `10 choose 2 = 45`
- positional matches per academy pair = `4`
- total matches = `45 x 4 = 180`

So the design materially understates operational size.

## Structural Critique of Rating Spreads, Phases, and Tiers

This is the deepest design issue.

### The current structure assumes spread implies structure

It currently assumes:

- low spread -> discovery
- medium spread -> transition
- high spread -> standard

That assumption is often false.

Two pools can both have a 300-point spread but be completely different:

Pool A:

- 21 players smoothly distributed from 900 to 1200

Pool B:

- 20 players clustered at 1200
- 1 outlier at 1500

Both have wide spread. Only Pool A supports meaningful tier-based structured scheduling.

### The current structure ignores density

A standard-tier algorithm only works if there are enough players in the relevant local neighborhoods.

The current phase gate does not ask:

- how many players are in each tier
- whether there are singleton tiers
- whether there are enough eligible 100-250 stretch partners
- whether the “core” spread is different from the raw spread

That is why `[1600, 1200, 1200, 1200]` can enter `STANDARD` and immediately produce a 400-gap match.

### The current structure ignores confidence / maturity

The design is explicitly about bootstrapping. But the phase gate ignores:

- rated-match counts
- confidence ratio
- whether the spread is based on stable ratings or just provisional noise

That makes the bootstrap fragile:

- a few early upset results can widen spread
- the pool flips into a more rigid phase too early

### The current structure is not aligned with configurable tiers

Tier boundaries are configurable in `rating_math.py`, but:

- phase thresholds are hardcoded in `fixture_engine.py`
- competitive/stretch thresholds are hardcoded in `fixture_engine.py`
- stretch caps are not tied to tier at all

So the system has two different rating structures:

1. configurable tiers
2. fixed scheduling bands

Those can drift apart.

### The current tier width is too coarse to stand in for fairness

A 200-point tier is reasonable for high-level reporting, but too wide to be the only pairing structure.

Inside one tier:

- 900 vs 1099 is same-tier but not a close match
- 1100 vs 1299 is same-tier but may still be a big development gap

For fixture generation, you need finer local neighborhoods than tier alone.

## Recommended Approach

## 1. Separate “pairing intent” from “actual gap band”

Do not overload one field to do everything.

Recommended fields per slot:

- `round_intent`: `COMPETITIVE` or `DEVELOPMENTAL`
- `gap_band`: `COMPETITIVE`, `STRETCH`, `OUT_OF_BAND`, `BYE`
- `player_a_role`: `PEER`, `STRETCHING`, `ANCHORING`, `BYE`
- `player_b_role`: same

That solves several current problems:

- anchor becomes explicit
- stretch rounds with 0-gap fallbacks are visible as fallbacks, not mislabeled stretch
- >250 gaps can be marked invalid or exceptional instead of pretending to be normal stretch

## 2. Replace ad hoc pair loops with constrained matching

For each round, build candidate edges and then choose a legal matching.

Constraints:

- each player appears at most once per round
- honor table capacity
- respect academy restrictions when required
- respect recent-rematch penalties
- minimize BYEs
- minimize out-of-band gaps

Scoring for candidate edges can combine:

- closeness to target gap
- same-tier / adjacent-tier preference
- academy preference
- rematch penalty
- bye-balance penalty
- recent developmental exposure balance

For the pool sizes here, a maximum-weight matching approach is the right tool. If you want something simpler, use greedy construction plus repair, but still enforce one-match-per-player as a hard invariant.

## 3. Redesign phase selection around robust pool shape, not raw max-min spread

Recommended session metrics:

- `core_spread = P90 - P10`
- tier occupancy counts
- count of players with low confidence / provisional status
- number of eligible competitive neighbors within 100 points
- number of eligible stretch partners within configured limits

Suggested gate:

1. `DISCOVERY`
   - use when most players are still provisional or `core_spread` is very small
   - also use for very small sessions, e.g. `< 6 players`

2. `TRANSITION`
   - use when some separation exists but there are not enough dense tier neighborhoods
   - split or cluster into 2-3 groups, but still use legal one-match-per-round pairing

3. `STANDARD`
   - use only when the pool has enough structure:
   - at least two viable local clusters or tiers
   - enough 0-100 competitive neighbors
   - enough 100-250 developmental candidates
   - singleton top or bottom players explicitly handled

This will stop outliers from hijacking the whole session.

## 4. Make stretch rules config-driven and tier-aware

Move these into configuration:

- competitive max gap
- tier-specific stretch min/max gaps
- max tolerated fallback gap
- min players required to activate standard mode
- max recent rematches allowed in a time window

Then use the same config for:

- tier assignment
- phase gating
- gap classification
- fallback rules

That removes the current split-brain between configurable tiers and hardcoded pairing thresholds.

## 5. Intra-academy redesign

### Discovery

- keep circle-method round-robin
- normalize input order explicitly so fixtures are deterministic
- use `round_offset` consistently

### Transition

- do not use the current `within_half_pairs()` logic
- split into halves or clusters, then generate a legal matching inside each half
- if one side has an extra player in cross-half developmental round, issue a BYE or nearest valid fallback explicitly

### Standard

- build competitive rounds from nearest-neighbor candidate edges, not only tier adjacency
- use tiers as a soft grouping aid, not the only structure
- if a tier is too small, merge with adjacent local neighborhood only when gap constraints allow it
- if no legal developmental partner exists, do not force one; schedule another competitive match or a BYE instead

## 6. Inter-academy redesign

### `TIER_MATCHED`

If the contract is “cross-academy inside tiers,” then make that a hard rule.

Recommended model:

- inside each tier, build a multipartite matching where same-academy edges are forbidden
- if a tier has only one academy represented:
  - either emit no pairings for that tier
  - or explicitly downgrade to an allowed fallback mode with a reason flag
- if a tier has a singleton player:
  - attempt adjacent-tier merge only within gap cap
  - otherwise BYE or carry-forward

Do not run a plain round-robin and hope interleaving is enough.

### `CROSS_ACADEMY_ONLY`

- replace round-robin-then-delete with direct cross-academy matching each round
- preserve academy constraint during any novelty repair
- add a feasibility check:
  - if one academy dominates the pool, surface that the strategy will generate many BYEs

### `TEAM_FORMAT`

- keep it as a separate competition product
- optionally allow lineup windows or seed-bands so #2 vs #1 anomalies can be corrected when rosters are unevenly sorted

### `FULL_ROUND_ROBIN`

- enforce the documented max player count or require explicit override
- label large-gap matches as out-of-band rather than generic stretch

## 7. Separate pairing generation from operational scheduling

This is especially important for inter-academy events.

Recommended pipeline:

1. generate legal pairings
2. estimate required rounds / waves from actual table capacity
3. assign matches into waves
4. only then assign physical table numbers

For intra-academy, replace binary `A/B` with numeric wave indexing:

- `wave_number = 1, 2, 3, ...`

If you want display labels, derive:

- `A, B, C, D, ...`

from that numeric wave.

## 8. Add invariant-based tests

The current test suite misses several important failures.

Examples of missing invariants:

- no player appears more than once per round
- every attending player appears exactly once per round as match or BYE
- stretch matches must stay within configured min/max
- `CROSS_ACADEMY_ONLY` must never output same-academy pairs, even after novelty repair
- `TIER_MATCHED` must not output same-academy pairs unless an explicit fallback flag is enabled
- singleton tiers must not silently disappear
- `round_offset` must shift round numbers in every phase
- wave numbering must remain unique when more than two waves are needed

Current tests are too permissive in a few places:

- transition test only checks the detected phase, not legal round structure (`test_fixture_engine.py:331-347`)
- category tests never assert behavior for gaps above 250 (`1126-1154`)
- some inter-academy tests already tolerate intra-academy behavior that the design says should not happen (`1028-1050`)

## Recommended Priority Order

1. Fix the transition phase so it always produces a legal round.
2. Redesign category labeling so round intent, gap band, and anchor/stretch role are not conflated.
3. Replace raw max-min phase gating with robust pool-shape metrics.
4. Rebuild `TIER_MATCHED` and `CROSS_ACADEMY_ONLY` around hard constraints instead of interleave-plus-repair heuristics.
5. Separate pairing generation from real table scheduling for league events.
6. Add invariant-driven tests before further feature expansion.

## Bottom Line

The design is strategically good, but the current implementation is still a prototype.

Its biggest strengths are:

- clear developmental intent
- sensible bootstrap ambition
- useful separation of event modes

Its biggest weaknesses are:

- illegal transition rounds
- unreliable category semantics
- brittle phase logic
- inter-academy strategy contracts that are not actually enforced

I would not treat the current engine as production-correct for competitive scheduling until the legality constraints, rating-structure model, and strategy guarantees are rebuilt around explicit matching and validation.
