# Fixture Engine Best-Of-Both Critique

## Purpose

This document merges the strongest points from:

- [jlrs_fixture_engine_critique.md](/c:/rallypoint/docs/jlrs_fixture_engine_critique.md)
- [fixture_generation_critique_by_gemini.md](/c:/rallypoint/docs/fixture_generation_critique_by_gemini.md)

It keeps:

- all high-confidence issues from my critique
- the Gemini issues I fully agree with
- the Gemini issues I partially agree with, reframed so they accurately reflect the current implementation
- some Gemini emphasis verbatim where it helps communicate operational risk

The goal is a single implementation-oriented critique that an agent can use to plan fixes safely.

## Reading Guide

Use this doc in three passes:

1. Fix correctness bugs first.
2. Fix strategy-contract and fairness violations next.
3. Then redesign thresholds, phase detection, and scheduling architecture.

Do not jump straight to new heuristics before fixing legality and invariants.

## Status (2026-05-28)

✅ **Phases 1-7 of the implementation plan landed.** All 22 numbered critique items are addressed in code; the engine moved from prototype-grade greedy heuristics to a constrained-matching solver with rematch policy, config-driven thresholds, an engine-internal rating-regime layer, pre-flight feasibility warnings, and a multi-wave session scheduler. See [docs/fixture_engine_phased_impl_plan.md](/c:/rallypoint/docs/fixture_engine_phased_impl_plan.md) for the per-phase commit history and `git log --grep="^Phase "` for the commits.

Per-item resolutions are marked inline below with **✅ Addressed in Phase N**.

## Executive Summary

The fixture engine has good strategic intent:

- bootstrap from flat ratings
- mix competitive and developmental matches
- support multiple inter-academy formats

But the current implementation is still prototype-grade in several important places.

The highest-priority problems are:

1. `generate_transition_fixtures()` can generate illegal rounds. **✅ Addressed in Phase 2**
2. match categories are semantically unreliable. **✅ Addressed in Phase 2 (additive round_intent / gap_band / role fields)**
3. standard-phase leftovers can create out-of-band pairings. **✅ Addressed in Phase 2 (OUT_OF_BAND label + max_exception_gap)**
4. `detect_phase()` is too brittle because it depends on raw `max - min` spread. **✅ Addressed in Phase 5 (P90-P10 + provisional-majority signal)**
5. inter-academy strategy guarantees are not actually enforced. **✅ Addressed in Phase 2 (constraint-aware novelty swap, TIER_MATCHED no-same-academy)**
6. inter-academy generation is not a true session scheduler. **✅ Addressed in Phase 3 (session_scheduler.py + wave_number)**

## Cross-Service Alignment Notes

This critique is intentionally fixture-engine-centric, but several surrounding services already implement related concepts. Any fix plan should respect those existing contracts rather than reintroducing them under different names without a migration path.

Important existing implementation that should be treated as baseline, not duplicated:

- visible player tiers are already centralized and reused across services via config-backed `get_tier()` / tier SQL
- provisional status and confidence already depend on total match evidence, not just raw rated matches:
  - `rated_matches_completed + virtual_matches`
  - `provisional_threshold`
  - `confidence_ratio = get_cr(total_matches, cfg)`
- rematch damping already exists downstream at match-processing time through `diminishing_signal_applied`
- `match_category` is already persisted and consumed by match submission, player history, and event fixture views
- submitted matches already enforce a hard `rating_eligible` cutoff at raw rating gap `> 500`

Implication:

- the recommendations below should generally be implemented as fixture-generation improvements and data-model extensions, not as silent replacement of service-layer semantics that other modules already depend on

## High-Confidence Correctness Bugs

### 1. Transition phase is illegal — ✅ Addressed in Phase 2

Relevant code:

- [fixture_engine.py](/c:/rallypoint/app/services/fixture_engine.py:230)
- especially [within_half_pairs()](/c:/rallypoint/app/services/fixture_engine.py:250)
- and [cross_pairs()](/c:/rallypoint/app/services/fixture_engine.py:272)

This is the clearest correctness failure in the file.

`within_half_pairs()` generates sliding adjacent windows rather than a legal one-match-per-player round.

For a half `[p1, p2, p3, p4]`, it can generate:

- `(p1, p2)`
- `(p2, p3)`
- `(p3, p4)`

That means `p2` and `p3` are each scheduled twice in the same round.

For odd total counts, `cross_pairs()` also leaves the extra player unscheduled rather than giving a BYE or explicit fallback.

Implementation direction:

- replace `within_half_pairs()` with a real one-match-per-player generator
- the simplest safe route is to reuse a true circle-method round-robin inside each half
- for odd cross-half rounds, explicitly emit a BYE or a legal fallback pair

Required invariant:

- every player appears at most once per round
- every attending player appears exactly once per round as either match or BYE

### 2. Match category semantics are broken — ✅ Addressed in Phase 2

Relevant code:

- [_category()](/c:/rallypoint/app/services/fixture_engine.py:101)
- [_assign_tables()](/c:/rallypoint/app/services/fixture_engine.py:109)
- [_assign_tables_league()](/c:/rallypoint/app/services/fixture_engine.py:622)

Relevant design:

- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:22)
- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:402)

Problems:

- the design defines `COMPETITIVE`, `STRETCH`, and `ANCHOR`
- the engine never emits `ANCHOR`
- `_category()` returns `STRETCH` for every gap above 100, with no upper bound
- stretch-intent rounds preserve the `STRETCH` label even when the actual gap is `0` or `400`

This makes downstream analytics and operator trust unreliable.

Implementation direction:

- separate `round_intent` from actual `gap_band`
- add explicit role semantics for the two participants
- do not immediately remove `match_category`, because other services already persist and expose it
- instead, introduce richer fields additively and preserve `match_category` as a compatibility field during migration

Recommended slot fields:

- `round_intent`: `COMPETITIVE` or `DEVELOPMENTAL`
- `gap_band`: `COMPETITIVE`, `STRETCH`, `OUT_OF_BAND`, `BYE`
- `player_a_role`: `PEER`, `STRETCHING`, `ANCHORING`, `BYE`
- `player_b_role`: same

Do not use a single `match_category` field to express all of those concepts at once.

Migration note:

- today, `match_service.py` persists slot `match_category` onto the match record, and `player_service.py` exposes it in player history and event fixtures
- so the safer path is:
  1. keep writing a compatibility `match_category`
  2. add richer fields such as `round_intent`, `gap_band`, and participant roles
  3. migrate downstream consumers only after those fields are fully wired through

### 3. Standard phase can create extreme leftover pairings — ✅ Addressed in Phase 2 + 4

Relevant code:

- [competitive_pairs()](/c:/rallypoint/app/services/fixture_engine.py:342)
- especially leftover handling at [380-385](/c:/rallypoint/app/services/fixture_engine.py:380)

The design says leftover odd players should be paired to the closest adjacent-tier player. The implementation does not do that. It just collects leftovers from each tier and pairs them in order.

That can create very large gaps, including gaps far outside the intended stretch zone.

Implementation direction:

- do not pair leftover players by list order alone
- move leftover handling into the same constrained matching logic as the rest of the round
- permit adjacent-tier fallback only when gap constraints allow it
- do not silently force an out-of-band match and label it as normal
- if no legal fallback exists in the current round, prefer a BYE over an undisclosed bad pairing
- but do not let isolated extreme players accumulate endless BYEs without escalation

Recommended isolation policy for extreme outliers:

1. use legal competitive or stretch pairings first
2. try adjacent-tier fallback within a configured soft cap
3. if still isolated, allow a controlled exception pairing within a separate configured `max_exception_gap`
4. label that exception explicitly as `OUT_OF_BAND` or `EXCEPTION`, not `COMPETITIVE` or `STRETCH`
5. only use a BYE when no acceptable exception exists

Recommended guardrails:

- `max_consecutive_byes_for_same_reason`
- `max_exception_gap`
- `exception_pairing_priority = least_bad_available_gap`

This matters because a strict “fallback else BYE” rule can strand the same top or bottom outlier repeatedly. The better principle is:

- avoid hidden bad matches
- avoid infinite isolation
- surface controlled exceptions transparently when repeated isolation would otherwise occur

Cross-service caution:

- the current match lifecycle already marks matches with raw rating gap `> 500` as not rating-eligible
- so any future `OUT_OF_BAND` / `EXCEPTION` policy must either stay within that existing hard cap or be introduced alongside an explicit coordinated change to `match_service.py`

### 4. `CROSS_ACADEMY_ONLY` can violate its own core contract — ✅ Addressed in Phase 2

Relevant code:

- [\_cross_academy_only()](/c:/rallypoint/app/services/fixture_engine.py:767)
- [\_swap_for_novelty()](/c:/rallypoint/app/services/fixture_engine.py:588)

`CROSS_ACADEMY_ONLY` is supposed to guarantee that every real match is cross-academy. That guarantee is broken by the novelty swap step, which optimizes only for rematches and does not preserve academy constraints.

This is a strategy-contract bug, not just a quality concern.

Implementation direction:

- first restore safety by treating novelty swapping as optional, not mandatory
- generate a valid cross-academy-only base schedule before attempting any novelty optimization
- only run novelty swapping when the pool has enough safe alternative cross-academy opponents left
- make the novelty step constraint-aware so it never creates same-academy pairs
- if the pool is saturated and safe novelty headroom is low, skip swapping and keep the valid base schedule

Required invariant:

- for `CROSS_ACADEMY_ONLY`, every non-BYE slot must satisfy `academy_a != academy_b`

Recommended staged policy:

1. build the legal `CROSS_ACADEMY_ONLY` round first
2. evaluate novelty headroom
3. only if headroom is high enough, attempt constraint-aware swaps
4. accept a swap only if:
   - both new pairs remain cross-academy
   - no player is duplicated
   - rematch quality improves or at least does not worsen
   - optional: rating-gap quality does not materially worsen
5. if no such swap exists, keep the original valid schedule

Recommended headroom signals:

- count of eligible cross-academy opponents a player has not recently played
- number of rematch-free alternative pairings available in the round
- academy-distribution skew, because dominant-academy pools usually have low safe swap room

This gives the engine both behaviors in the right order:

- correctness first
- novelty optimization only when the pool actually has room for it

### 5. `TIER_MATCHED` does not enforce its documented strategy — ✅ Addressed in Phase 2

Relevant code:

- [\_tier_matched()](/c:/rallypoint/app/services/fixture_engine.py:717)
- [\_run_circle_round_robin()](/c:/rallypoint/app/services/fixture_engine.py:657)

The design says that when 2 or more academies are present in a tier, the system should run cross-academy pairings and skip intra-academy ones. The implementation does not enforce that. It interleaves players and runs a normal round-robin, which still yields intra-academy matches.

Implementation direction:

- stop using plain round-robin as the engine for this strategy
- inside each tier, build a legal matching with same-academy edges forbidden
- if a fallback mode is allowed, surface it explicitly in the output rather than silently breaking the strategy promise

### 6. Singleton tiers can disappear silently — ✅ Addressed in Phase 2 (`_absorb_singleton_tiers`)

Relevant code:

- [\_tier_matched()](/c:/rallypoint/app/services/fixture_engine.py:745)

If a tier contains only one player, the engine simply skips that tier and the player disappears from the output.

Implementation direction:

- singleton tiers must produce one of:
- an adjacent-tier fallback within allowed gap
- a controlled exception pairing within `max_exception_gap`
- an explicit BYE as the final fallback

Silent disappearance is not acceptable.

Live-event policy clarification:

- if a player is registered and present at the venue, `carry-forward / unscheduled` should not be the normal fallback
- for present players, prefer:
  1. normal same-tier pairing
  2. adjacent-tier fallback within normal gap rules
  3. explicit `OUT_OF_BAND` / `EXCEPTION` pairing within `max_exception_gap`
  4. BYE only if no acceptable exception exists

Implementation direction for singleton tiers in live events:

- detect the singleton tier
- search first for a same-tier or adjacent-tier legal pairing
- if none exists, search the broader pool for the least-bad available opponent within `max_exception_gap`
- if such an opponent exists, create an explicitly labeled `OUT_OF_BAND` / `EXCEPTION` match
- if no opponent satisfies that exception cap, emit a BYE with a reason such as `singleton_tier_no_eligible_opponent`

Required guardrails:

- `max_exception_gap`
- `exception_pairing_priority = least_bad_available_gap`
- exception matches must never be mislabeled as normal `COMPETITIVE` or `STRETCH`

## Structural Design Problems

### 7. "Whole-Pool Phase Flaw" — ✅ Addressed in Phase 5

Gemini’s emphasis is worth preserving here:

> “Whole-Pool Phase Flaw”

Relevant code:

- [detect_phase()](/c:/rallypoint/app/services/fixture_engine.py:33)

`detect_phase()` uses only:

```text
spread = max(rating) - min(rating)
```

This is too fragile for real attendance patterns.

One outlier can push the whole session into `STANDARD`, even when the core pool is effectively homogeneous.

This is one of the most important structural problems in the engine.

Implementation direction:

- replace raw spread gating with a more robust pool-shape decision

Recommended session metrics:

- `core_spread = P90 - P10`
- tier occupancy counts
- count of provisional / low-confidence players
- number of eligible competitive neighbors within the competitive gap
- number of eligible developmental partners within the stretch gap

Suggested gating:

1. `DISCOVERY`
   - use when most players are provisional or `core_spread` is very small
   - also use for very small sessions

2. `TRANSITION`
   - use when there is some separation but not enough local density for standard-tier logic

3. `STANDARD`
   - use only when the pool has enough local structure to support it

### 8. "The Scaling Flaw" — ✅ Addressed in Phase 5 (`rating_regime.py` + `fixture_config.py`)

Gemini’s emphasis is also useful here:

> “The Scaling Flaw”

And more specifically:

> “The hardcoded boundaries (`_COMPETITIVE_MAX = 100`, `_STRETCH_MAX = 250`) are fragile when used across a real academy setup due to how rating differentials scale across skill levels.”

I agree with the core concern, with one caveat:

- static thresholds are too blunt
- but average-rating-only scaling is not enough by itself to solve the problem
- and Gemini’s suggested scale should not be treated as a direct drop-in replacement for the current visible tier system

This problem shows up in several ways:

- same-tier does not imply competitive
- 100 points may be too wide in elite pools
- 100 points may be too narrow in low-confidence beginner pools
- the design’s tier-specific stretch limits are not implemented at all

Implementation direction:

- move thresholds into config
- allow tier-aware or band-aware overrides
- use the same config source for phase gating, tier grouping, gap classification, and fallback policy
- do not collapse the current program tiers directly into a new four-band scale without separating product semantics from engine behavior

Do not keep one rating structure for tiers and a separate hardcoded structure for scheduling.

Recommended two-layer approach:

1. keep the current user-facing / program tier taxonomy:
   - `BEGINNER`
   - `INTERMEDIATE`
   - `ADVANCED`
   - `ELITE`
   - `NATIONAL_TRACK`
2. add a second engine-facing rating-regime layer that controls pairing behavior:
   - `VOLATILE_LOW`
   - `DEVELOPING`
   - `HIGH_LEVEL`
   - `ELITE_PROXIMITY`

Why this split is better:

- the current tiers appear to serve product, academy, and reporting purposes
- `NATIONAL_TRACK` looks like a meaningful program concept, not just a rating bucket
- Gemini’s “typical table tennis rating scale” is more useful as a model of how gap sensitivity changes across rating bands than as a direct replacement for your domain model
- the engine needs behavior calibration more than it needs renamed visible tiers

How the two layers should work together:

- visible tiers remain stable for UI, communication, eligibility, and reporting
- engine-facing regimes drive:
  - competitive-gap thresholds
  - stretch-gap thresholds
  - exception-gap policies
  - phase-gating sensitivity
  - rematch tolerance and BYE tolerance tuning if desired

Example mapping direction:

- current visible tier:
  - `BEGINNER`
  - `INTERMEDIATE`
  - `ADVANCED`
  - `ELITE`
  - `NATIONAL_TRACK`

- engine-facing regime examples:
  - ratings roughly `0-800` -> `VOLATILE_LOW`
  - ratings roughly `800-1400` -> `DEVELOPING`
  - ratings roughly `1400-2000` -> `HIGH_LEVEL`
  - ratings roughly `2000+` -> `ELITE_PROXIMITY`

Important note:

- those engine-regime boundaries should be configurable
- they should not be hardcoded as a new visible replacement tier system without validating them against your current rating distribution and product semantics

Concrete first-pass regime definitions:

These should be defined as engine-only pairing regimes, not as new business tiers.

Recommended input dimensions:

- absolute rating
- rating maturity, such as:
  - `total_matches = rated_matches_completed + virtual_matches`
  - `CR` / confidence ratio
  - provisional status

This matters because a `950` player with 3 total-evidence matches is not the same pairing problem as a `950` player with 80 total-evidence matches.

Cross-service note:

- this already aligns with the current player/rating services, which compute maturity from total evidence and not just raw rated matches
- the regime layer should therefore reuse the existing maturity signals rather than inventing a competing notion of provisional/confidence

Recommended first-pass thresholds:

### `VOLATILE_LOW`

Suggested first-pass rule:

- `rating < 900`
- or `total_matches < provisional_threshold`
- or equivalently low confidence / clearly provisional status

Meaning:

- ratings are still noisy
- rating gaps should be interpreted loosely
- relatively wide gaps can still be competitively plausible

Recommended behavior:

- wider competitive-gap allowance
- wider stretch-gap allowance
- stronger preference for opponent diversity and information gain
- do not overreact to small rating differences

### `DEVELOPING`

Suggested first-pass rule:

- `900 <= rating < 1400`
- unless very low confidence still keeps the player in `VOLATILE_LOW`

Meaning:

- this is the main academy-development band
- ratings are meaningful but still moderately elastic
- this should be the baseline regime for current gap policy

Recommended behavior:

- current standard competitive/stretch assumptions can live here as the baseline
- use this regime as the anchor for default threshold tuning

### `HIGH_LEVEL`

Suggested first-pass rule:

- `1400 <= rating < 2000`
- with moderate to high confidence

Meaning:

- ratings are more stable
- smaller gaps matter more
- a 100-point difference is more meaningful than in the developing band

Recommended behavior:

- narrower competitive-gap allowance
- narrower stretch-gap allowance
- stricter rematch tolerance when alternatives exist

### `ELITE_PROXIMITY`

Suggested first-pass rule:

- `rating >= 2000`
- or `NATIONAL_TRACK` with sufficiently high confidence
- or a future percentile-based top-band rule if your actual ladder compresses lower

Meaning:

- small differences can already be significant
- exception matches should be rare
- top-end isolation needs careful handling, but bad pairings are especially costly

Recommended behavior:

- tight competitive-gap cap
- tight stretch-gap cap
- strict exception-gap policy
- careful handling of repeated BYEs versus out-of-band exceptions

Important calibration note:

- if your actual player ecosystem rarely reaches `2000+`, do not hardcode `ELITE_PROXIMITY` to absolute rating alone
- use a hybrid trigger such as:
  - absolute threshold
  - top percentile of active rated players
  - or `NATIONAL_TRACK` plus confidence

What these regimes should control:

- `competitive_max_gap`
- `stretch_min_gap`
- `stretch_max_gap`
- `max_exception_gap`
- rematch tolerance
- BYE tolerance / isolation escalation

What they should not control directly:

- the visible program tier label shown to users
- academy or product eligibility categories
- reporting labels unless the product later chooses to surface them explicitly

Practical recommendation:

- do not replace the existing `BEGINNER / INTERMEDIATE / ADVANCED / ELITE / NATIONAL_TRACK` scale immediately
- instead, introduce the engine-facing regime layer and use it to calibrate dynamic pairing behavior
- only revisit the visible tier taxonomy later if product/reporting needs independently justify it

Important distinction: rating regimes are not the same thing as scheduling phases.

- scheduling phases answer:
  - “what pairing algorithm should the session use right now?”
  - examples: `DISCOVERY`, `TRANSITION`, `STANDARD`
- rating regimes answer:
  - “how should rating gaps be interpreted at this skill level?”
  - examples: `VOLATILE_LOW`, `DEVELOPING`, `HIGH_LEVEL`, `ELITE_PROXIMITY`

In other words:

- phase = workflow mode
- regime = calibration layer

They operate at different levels:

- phase is primarily a session-level decision
- regime is primarily a player-level or local-pool-level behavior model

Example:

- 16 players all around 1000 may still sit in a `DEVELOPING` rating regime
- if they are tightly clustered and ratings are not yet informative, the session phase may still be `DISCOVERY`

Later:

- the same academy population may still mostly be in the `DEVELOPING` regime
- but once enough structure emerges in the pool, the session phase can move to `STANDARD`

So the regime does not replace the phase. Instead:

1. detect session phase
2. choose the pairing algorithm for that phase
3. use rating regime to calibrate thresholds inside that algorithm

Do not collapse these two concepts into one layer.

Important distinction: intra-academy phases should not be reused wholesale as the top-level controller for inter-academy events.

Why:

- `DISCOVERY / TRANSITION / STANDARD` was designed to solve an intra-academy bootstrapping problem:
  - flat or weak internal ratings
  - repeated local sessions
  - deciding when a local pool is mature enough to move from round-robin discovery into structured rating-based pairing
- inter-academy events usually solve a different problem:
  - fair cross-academy comparison
  - team-vs-team competition
  - cross-academy exposure
  - external calibration between otherwise separate academy ecosystems

In other words:

- intra-academy is primarily phase-driven
- inter-academy should be primarily strategy-driven

Why the same phase model is a poor top-level fit for inter-academy:

1. the original phases depend on internal rating separation logic
   - they ask whether a local academy pool has separated enough to trust structured pairings
2. inter-academy pools can have large combined spread for reasons that do not imply “standard intra-academy mode”
   - a strong academy and a weaker academy can create a large event-wide spread immediately
   - that spread does not by itself answer which inter-academy format should be used
3. inter-academy choice is already format-driven in the current product
   - `TIER_MATCHED`
   - `CROSS_ACADEMY_ONLY`
   - `TEAM_FORMAT`
   - `FULL_ROUND_ROBIN`
4. inter-academy often needs cross-academy exposure logic, not intra-academy bootstrap logic
   - a player may have a mature overall rating but low external evidence against other academies
   - that should affect pairing caution, not force the entire event into an intra-academy phase label

Recommended distinction:

- intra-academy:
  - use `DISCOVERY / TRANSITION / STANDARD` as the primary session-level scheduler mode
  - then use regime to calibrate thresholds inside the chosen phase
- inter-academy:
  - use event strategy as the primary top-level mode
  - then apply maturity/exposure overlays to tune thresholds, caution levels, rematch handling, and exception policy

Recommended inter-academy control stack:

1. choose event strategy
   - `TIER_MATCHED`
   - `CROSS_ACADEMY_ONLY`
   - `TEAM_FORMAT`
   - `FULL_ROUND_ROBIN`
2. evaluate pool maturity and cross-academy exposure
3. use rating regime to calibrate gap sensitivity
4. apply rematch, exception, and BYE policies consistent with the chosen strategy

Suggested inter-academy supplemental signals:

- `cross_academy_matches`
- `distinct_external_academies_faced`
- optional `cross_academy_confidence`

These signals should not replace the global rating regime. They should act as inter-academy caution overlays.

### 9. Tier width and fairness width are misaligned — ✅ Addressed in Phase 5 (per-regime gap caps)

Relevant code:

- [get_tier()](/c:/rallypoint/app/utils/rating_math.py:70)
- [fixture thresholds](/c:/rallypoint/app/services/fixture_engine.py:27)

Default tiers are 200 points wide, while competitive pairing is 100 points wide. That means players can be in the same tier and still produce a `STRETCH` match under the current engine.

This matters because `TIER_MATCHED` implicitly sells “same-tier” as “fair” or “peer-level,” which is not consistently true.

Implementation direction:

- treat tiers as a coarse grouping aid
- do not treat tier boundaries as the final fairness mechanism
- use finer local neighborhoods for actual pairing

### 10. `stretch_pairs()` has a greedy range-scan flaw — ✅ Addressed in Phase 2 (monotonic short-circuit) + Phase 4 (solver)

This is one of the useful implementation-level catches from the Gemini critique and should be preserved explicitly.

Relevant code:

- [stretch_pairs()](/c:/rallypoint/app/services/fixture_engine.py:389)

The current sweep assumes that if a candidate partner is too far away, the loop can keep scanning “closer.” But for a fixed `pid_a`, the player list is sorted by descending rating, and `pid_b` moves farther down the list as `offset` increases.

That means:

- the rating gap is monotonic non-decreasing for that search direction
- once `gap > _STRETCH_MAX`, continuing the scan will not find a closer partner
- the loop is then searching in the wrong direction, wasting work and sometimes failing late rather than exiting early

This is the Gemini point in plain terms:

> “If a top-tier player has an outlier rating, scanning down the array increases the rating gap. The loop keeps searching in the wrong direction, wastes computation time, and ends up failing to find a partner.”

Example:

- sorted ratings: `1600, 1400, 1300, 1200, 1100`
- suppose `pid_a = 1600`
- normal stretch band is `100 < gap <= 250`

Search results as the loop moves downward:

- vs `1400` -> gap `200` -> valid
- vs `1300` -> gap `300` -> already too large
- vs `1200` -> gap `400` -> even worse
- vs `1100` -> gap `500` -> even worse

Once the loop reaches the `300`-gap case, continuing to scan does not move back toward legality. It only moves farther away.

Why it matters:

- wastes computation
- makes the intent of the search misleading
- can produce confusing fallback behavior for outlier players

Implementation direction:

- once the search for a fixed `pid_a` reaches `gap > _STRETCH_MAX`, short-circuit that direction
- do not keep scanning downward under the assumption that a closer candidate may appear later
- if you need a broader search, do it intentionally through a different candidate-generation strategy rather than continuing a monotonic failure path
- ideally, replace this kind of one-direction greedy scan with constrained candidate generation plus matching, so legal stretch options are identified systematically

## Practicality And Scheduling Problems

### 10. "Resource-Time Capacity Mismatch" — ✅ Addressed in Phase 3 (`session_scheduler.py` + `num_tables` plumbing)

Gemini’s phrase is useful, but it needs to be framed correctly:

> “Resource-Time Capacity Mismatch”

I partially agree with Gemini here.

This is a real problem for **inter-academy generation**, not for the whole engine.

Intra-academy generation:

- does compute `num_rounds` from [calculate_session_capacity()](/c:/rallypoint/app/services/fixture_engine.py:59)
- does limit the phase generators through [generate_fixtures()](/c:/rallypoint/app/services/fixture_engine.py:509)

Inter-academy generation:

- ignores session minutes
- ignores table count
- ignores wave count
- returns pairing matrices, not executable schedules

Implementation direction:

- split the system into two stages:
  1. pairing generation
  2. operational scheduling

For inter-academy events, add a scheduler layer that:

- receives total pairings
- receives table count and session capacity
- converts pairings into waves and table assignments

### 11. `_assign_tables()` only handles two waves — ✅ Addressed in Phase 3 (numeric `wave_number`, A/B is derived legacy display)

Relevant code:

- [\_assign_tables()](/c:/rallypoint/app/services/fixture_engine.py:125)

This function assumes that if there are more pairs than tables, there are only two sub-rounds: `A` and `B`.

That breaks once a round requires three or more waves.

Implementation direction:

- replace `sub_round: "A" | "B"` logic with numeric `wave_number`
- if a display label is needed, derive `A/B/C/...` from the numeric value

This is the real `_assign_tables()` problem worth fixing first.

### 12. `round_offset` is not applied consistently — ✅ Addressed in Phase 2

Relevant code:

- [generate_fixtures()](/c:/rallypoint/app/services/fixture_engine.py:509)

`round_offset` only affects discovery fixtures. Transition and standard restart numbering from 1.

Implementation direction:

- make `round_offset` part of every phase generator’s interface
- ensure returned rounds are consistent across sessions

### 13. `matches_per_player` is not a guaranteed schedule property — ✅ Addressed in Phase 3 (`matches_per_player_estimate` exposed)

Relevant code:

- [calculate_session_capacity()](/c:/rallypoint/app/services/fixture_engine.py:59)
- [generate_fixtures()](/c:/rallypoint/app/services/fixture_engine.py:544)

The value is only a reporting metric. Actual participation can differ because of:

- BYEs
- odd pools
- inter-academy strategy constraints
- missing players in buggy transition rounds

Implementation direction:

- either rename this field to reflect that it is an estimate
- or redesign schedule generation so the returned field becomes a true guaranteed minimum/target

## Fairness And Format-Limit Problems

### 14. Gemini's Four Fairness Frames — ✅ Addressed in Phase 6 (preflight warnings expose all four)

Gemini grouped several fairness problems under four strongly worded labels. Those labels are useful, so I am preserving them here with implementation-facing examples and current-code qualification.

#### Issue A: “`_cross_academy_only` Teammate Spikes”

Quoted emphasis from Gemini:

> “If the circle method pairs two players from the same academy, the engine immediately gives both players an individual round BYE. If a dominant academy brings 75% of the total players, its participants get stuck in consecutive rounds of sitting out, killing tournament engagement.”

Current-code basis:

- [\_cross_academy_only()](/c:/rallypoint/app/services/fixture_engine.py:767)

Example:

- Academy A: `a1, a2, a3, a4`
- Academy B: `b1`

In this kind of `4 vs 1` pool, only one cross-academy match can exist in many rounds. The rest of Academy A is repeatedly pushed into BYEs because same-academy collisions are stripped out.

Why it matters:

- present players spend too much of the event idle
- `cross_academy_pct` can still look excellent while the actual participation experience is poor
- the format becomes a bad fit for dominant-academy distributions

Implementation direction:

- add a pre-flight feasibility warning for dominant-academy pools
- surface likely BYE burden before generating fixtures
- consider rejecting or downgrading the strategy when the pool is too skewed
- prefer to skip novelty swapping entirely in heavily saturated or highly skewed pools, because there is usually too little safe swap headroom for it to help

#### Issue B: “`_team_format` Lineup Bottlenecks”

Quoted emphasis from Gemini:

> “Matches are made strictly by rank index matching (`pos`). If Academy A brings 8 players and Academy B brings 2 players, positions 3 through 8 for Academy A instantly receive a non-playing BYE slot for that round block.”

Current-code basis:

- [\_team_format()](/c:/rallypoint/app/services/fixture_engine.py:819)

Example:

- Academy A: `a1, a2, a3, a4, a5, a6, a7, a8`
- Academy B: `b1, b2`

`TEAM_FORMAT` pairs:

- `a1 vs b1`
- `a2 vs b2`
- `a3 BYE`
- `a4 BYE`
- `a5 BYE`
- `a6 BYE`
- `a7 BYE`
- `a8 BYE`

Why it matters:

- this is not a correctness bug, but it is a severe format limitation in uneven-roster events
- coaches may assume a “team event” means broad participation, when positional matching can bench much of a large roster

Implementation direction:

- document this explicitly in the strategy contract
- optionally add alternate lineup policies for large roster imbalance
- keep it separate from correctness fixes

#### Issue C: “`_tier_matched` Odd-Number Islands”

Quoted emphasis from Gemini:

> “When parsing players into separate rating tiers, any tier left with an odd number of players (e.g., an Elite Tier of 5) becomes an isolated ecosystem. Because an odd group cannot pair up perfectly, one player in that tier is mathematically forced to take a BYE every single round, leaving them stranded even if tables are empty elsewhere.”

Current-code basis:

- [\_tier_matched()](/c:/rallypoint/app/services/fixture_engine.py:717)

Qualification:

- the BYE burden is real
- but in a true round-robin that BYE rotates, so it is not literally the same player every round

Example:

- Elite tier contains:
  - Academy A: `a1, a2`
  - Academy B: `b1, b2`
  - Academy C: `c1`

The tier has 5 players, so after BYE padding one player will sit each round. Over time that rotation is fairer than Gemini’s wording suggests, but the tier is still a small isolated pool with recurring BYE friction.

Why it matters:

- small odd-size tiers produce repeated idle time
- the issue is more visible when adjacent tiers are thin and no reasonable merge exists

Implementation direction:

- detect isolated odd-size subpools
- allow adjacent-tier merge only within a gap cap
- otherwise surface expected BYE burden to the operator

#### Issue D: “`_tier_matched` Infrastructure Starvation”

Quoted emphasis from Gemini:

> “If Tier 1 has 12 players (demanding 6 concurrent tables) and Tier 2 has 4 players (demanding 2 concurrent tables), running this round concurrently requires 8 tables. If the venue only has 4 tables, Tier 1 overloads the capacity pool. Sub-rounds will generate heavy backlogs, drastically increasing downtime for the isolated players in smaller tiers.”

Qualification:

- this is a useful scheduling warning
- but it does **not** describe the current implementation exactly, because current `TIER_MATCHED` serializes tier rounds with `round_offset` rather than running tier rounds concurrently

Why still keep it:

- it is a valid caution for any future event-day scheduler that tries to execute tier rounds as if they were concurrent blocks
- it also captures the more general reality that pool structure can create poor utilization and waiting-time asymmetry

Example if a future scheduler were to run tier rounds concurrently:

- Tier 1: 12 players -> 6 matches
- Tier 2: 4 players -> 2 matches
- Venue: 4 tables

If a scheduler naïvely attempts both tiers at once, it would need 8 tables to avoid queueing. With only 4 tables, some players would wait through multiple waves and smaller tiers could be delayed behind larger ones.

Implementation direction:

- if a future inter- or intra-tier scheduler supports concurrent tier execution, it must model table contention explicitly
- pre-flight checks should estimate wave count, waiting-time spread, and tier-level backlog before publishing a schedule

### 15. "Sit-out" spikes in `CROSS_ACADEMY_ONLY` — ✅ Addressed in Phase 6 (preflight `DOMINANT_ACADEMY_BYE_BURDEN` warning)

Gemini’s wording is fair and worth preserving:

> “sit-out spikes”

When one academy dominates the pool, same-academy collisions are converted to BYEs and that academy can absorb large idle periods.

This is not just a UX complaint. It changes the effective match volume and can make the strategy unsuitable for certain academy distributions.

Implementation direction:

- add a pre-flight feasibility warning for dominant-academy pools
- surface likely BYE burden before generating fixtures
- consider rejecting or downgrading the strategy when the pool is too skewed
- prefer to skip novelty swapping entirely in heavily saturated or highly skewed pools, because there is usually too little safe swap headroom for it to help

### 15. "Lineup Bottlenecks" in `TEAM_FORMAT` — ✅ Addressed in Phase 6 (preflight `TEAM_FORMAT_LINEUP_IMBALANCE`)

Gemini’s emphasis:

> “Lineup Bottlenecks”

This is real, but it should be treated as a format limitation rather than a raw bug.

`TEAM_FORMAT` pairs by rank position. Uneven rosters naturally create unmatched positions and BYEs.

Implementation direction:

- document this explicitly in the strategy contract
- optionally add alternate lineup policies for large roster imbalance
- keep it separate from correctness fixes

### 16. "Odd-Number Islands" — ✅ Addressed in Phase 6 (preflight `ODD_TIER_ISLAND`)

Gemini’s phrase:

> “Odd-Number Islands”

I only partially agree with Gemini’s framing, but it is still worth including because it points to a real fairness burden.

Clarification:

- odd-size tier pools do produce one BYE per round
- that BYE rotates, so the same player is not permanently stranded
- but repeated isolated BYE burden in small odd-size tiers is still a practical fairness issue

Implementation direction:

- detect isolated odd-size subpools
- allow adjacent-tier merge only within a gap cap
- otherwise surface expected BYE burden to the operator

### 17. Rematch control is weaker than the design implies — ✅ Addressed in Phase 4 (`rematch_policy.py` harm-score + solver fallback)

Relevant design:

- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:285)

Relevant code:

- [stretch exclude logic](/c:/rallypoint/app/services/fixture_engine.py:396)
- [session pair recording](/c:/rallypoint/app/services/fixture_engine.py:497)
- [novelty swap](/c:/rallypoint/app/services/fixture_engine.py:588)
- [diminishing signal check](/c:/rallypoint/app/services/match_service.py:60)
- [effective event type downgrade](/c:/rallypoint/app/utils/rating_math.py:250)

The design speaks in terms of recent-match avoidance. The current system does already have a downstream rematch-damping mechanism through `diminishing_signal_applied`, but fixture generation itself still only has thin pair-set control in selected places.

That distinction matters:

- match-processing already softens repeated-pair rating impact after the fact
- fixture generation still needs its own pairing-time rematch policy so the scheduler avoids bad repeats when feasible instead of relying only on downstream damping

Implementation direction:

- make rematch control a full-system rule when feasible, not a strategy-specific afterthought
- move to explicit recent-match counts and time windows
- apply rematch penalties or hard caps consistently across all phases and strategies
- define a common rematch policy layer that every generator consults before finalizing pairings
- treat this as a complement to the existing diminishing-signal system, not a replacement for it

Recommended rule shape:

- if a non-rematch legal pairing exists, prefer it over a recent rematch
- if only rematches are available, choose the least harmful rematch rather than failing the round
- allow stricter rematch avoidance in larger pools and more relaxed rematch tolerance in saturated pools
- keep rematch control subordinate to hard legality constraints:
  - one match per player per round
  - academy restrictions when required
  - gap caps and exception caps

Recommended common rematch inputs:

- `recent_match_counts[(a, b)]`
- `recent_match_window_days`
- `max_recent_matches_same_pair`
- `rematch_penalty_weight`
- `pool_saturation_threshold`

Recommended definition of “least harmful rematch”:

- if rematches are unavoidable, choose the legal rematch with the lowest combined harm score
- lower harm should generally mean:
  - the pair has not played very recently
  - the pair has not repeated many times in the recent window
  - the pairing still has acceptable gap quality
  - the pairing does not repeat the same exact session context if avoidable
  - the pairing helps avoid disproportionate BYE burden for isolated players

Recommended harm factors:

1. recency
   - a pair that played 20 days ago is less harmful than a pair that played yesterday
2. repeat count
   - a pair that has met once recently is less harmful than a pair that has met 3 times recently
3. session duplication
   - a same-session repeat is usually the most harmful and should normally be treated as disallowed or near-disallowed
4. context repetition
   - repeating the same players in the same strategic context is more harmful than repeating them in a different context
5. gap quality
   - among unavoidable rematches, the pairing with the better gap quality is usually less harmful
6. BYE avoidance benefit
   - a rematch may be less harmful than giving a player repeated isolation BYEs

Important hard limits:

- “least harmful rematch” does not mean “break legality to avoid a rematch”
- strategy-contract violations remain worse than rematches
- same-academy pairings in `CROSS_ACADEMY_ONLY` remain invalid
- one-match-per-player-per-round remains non-negotiable
- exception-gap caps still apply

Example 1:

- `A-B`
  - played yesterday
  - 3 recent meetings
  - 35-point gap
- `A-C`
  - played 14 days ago
  - 1 recent meeting
  - 60-point gap
- `A-D`
  - played 10 days ago
  - 1 recent meeting
  - 220-point gap

If all three are legal rematches and a rematch is unavoidable, `A-C` is usually the least harmful:

- much less recent than `A-B`
- fewer repeats than `A-B`
- materially better gap quality than `A-D`

Example 2:

- `T-U`
  - rematch from 9 days ago
  - 1 prior meeting
  - 70-point gap
- `T-BYE`
  - would be the third consecutive BYE for `T`
- `T-V`
  - fresh opponent
  - but 340-point gap, outside normal rules

If `T-V` exceeds allowed exception limits, then `T-U` may be the least harmful outcome:

- it preserves legality
- it avoids repeated isolation
- it is less harmful than either an invalid pairing or another avoidable BYE

Suggested scoring shape:

- `harm = recency_penalty + repeat_count_penalty + same_session_penalty + context_repeat_penalty + gap_deviation_penalty - bye_relief_credit`

Agents implementing this do not need to use that exact formula, but they should make the ranking logic explicit and testable.

Recommended phase/strategy expectation:

- `DISCOVERY`: prefer fresh opponents strongly, because information gain is the point of the phase
- `TRANSITION`: avoid same-session and recent repeats when legal alternatives exist
- `STANDARD`: apply rematch penalties to both competitive and developmental rounds
- `TIER_MATCHED`: avoid recent same cross-academy repeats within the tier when safe alternatives exist
- `CROSS_ACADEMY_ONLY`: use the gated, constraint-aware novelty optimization described above
- `TEAM_FORMAT`: rematch control may be weaker because the format itself constrains opponent choice, but repeats should still be surfaced and minimized when roster structure allows

## Design Doc vs Implementation Mismatches

These are important because they mislead future agents and maintainers.

### 18. Phase boundaries do not exactly match the design text — ✅ Addressed in Phase 2

Relevant design:

- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:146)
- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:219)

Relevant code:

- [detect_phase()](/c:/rallypoint/app/services/fixture_engine.py:33)

Mismatches:

- design says discovery trigger is `<= 100`, code uses `< 100`
- design says standard trigger is `> 250`, code uses `>= 250`

### 19. Small-session fallback behavior does not match the design — ✅ Addressed in Phase 2 (`< 6` players route to round-robin)

Relevant design:

- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:340)

The design says fewer than 6 players should use pure round-robin. The code still routes small sessions through spread-based phase detection.

### 20. Discovery ordering is not normalized — ✅ Addressed in Phase 2 (`_circle_round` sorts by `player_id`)

Relevant design:

- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:152)

Relevant code:

- [\_circle_round()](/c:/rallypoint/app/services/fixture_engine.py:168)

The design says deterministic non-rating ordering. The code uses incoming list order without normalizing it.

### 21. Cross-academy monthly Swiss-like logic is documented but not implemented — ⏸ Deferred

Relevant design:

- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:614)

There is no Swiss-style meet logic in the current engine.

### 22. `TEAM_FORMAT` scale is understated in the design example — ✅ Addressed in Phase 7 (see design-doc fix below)

Relevant design:

- [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:561)

The example implying “10 academies x 4 players = 40 matches in 45 rounds” is mathematically wrong.

Correctly:

- academy pairings: `10 choose 2 = 45`
- matches per pairing: `4`
- total matches: `180`

## Recommended Implementation Strategy

## Phase 1: Add invariants and failing tests first

Before redesigning heuristics, add tests for:

- no player appears more than once in a round
- every attending player appears exactly once per round as match or BYE
- `CROSS_ACADEMY_ONLY` never emits same-academy pairs
- `TIER_MATCHED` never emits same-academy pairs unless explicit fallback mode is enabled
- singleton tiers never disappear
- `round_offset` is honored in every phase
- multi-wave rounds generate unique wave numbering
- out-of-band gaps are surfaced explicitly
- rematch control is applied across the full system when feasible, not only in `CROSS_ACADEMY_ONLY`
- if a non-rematch legal pairing exists, the generator should prefer it over a recent rematch
- if the pool is saturated and rematches are unavoidable, the generator should choose the least harmful rematch rather than breaking legality or strategy constraints

## Phase 2: Fix correctness bugs

Fix in this order:

1. transition legality
2. category semantics
3. `CROSS_ACADEMY_ONLY` novelty-swap contract break
4. singleton-tier disappearance
5. multi-wave scheduling

When fixing step 3:

- first disable or bypass unsafe novelty swapping
- then reintroduce it only as a gated, constraint-aware optimization

## Phase 3: Rebuild pairing logic around constrained matching

For each round:

1. build candidate edges
2. score them
3. enforce hard constraints
4. choose a legal matching

Hard constraints:

- one match per player per round
- academy restrictions when required
- table/wave limits
- gap caps when required

Soft scoring:

- closeness to target gap
- same-tier or adjacent-tier preference
- rematch penalty
- BYE-balance penalty
- developmental-exposure balance
- isolation-exception penalty, so explicit exception matches are used only after better options are exhausted

When unavoidable rematches remain after hard constraints are applied, the solver should rank them using an explicit least-harmful-rematch rule rather than a vague “best available” fallback.

For `CROSS_ACADEMY_ONLY`, novelty improvement should be treated as a second-pass optimization on top of a legal matching, not as a primary generator goal.

For the full system, rematch control should usually be modeled as a soft penalty with a configurable hard cap in extreme cases, rather than as one-off local heuristics attached to a single strategy.

## Phase 4: Redesign phase detection and threshold config

Do this only after legality and strategy contracts are fixed.

Implement:

- robust phase gating
- config-driven thresholds
- tier-aware and pool-aware developmental limits

## Agent Notes

If another agent implements this, they should avoid these traps:

1. Do not patch `_assign_tables()` first and assume the legality issue is solved. The main illegal-round bug is in transition generation.
2. Do not treat current `match_category` semantics as sufficient. The representation needs redesign, but the rollout should be additive and migration-safe because other services already depend on `match_category`.
3. Do not keep plain round-robin as the engine for `TIER_MATCHED` if cross-academy-only behavior is a hard contract.
4. Do not add dynamic thresholds without first unifying the config story for tiers, gap bands, and phase detection.
5. Do not optimize inter-academy pair generation before deciding whether the system is returning a pairing matrix or a real schedule.
6. Do not run rematch-reduction swaps in `CROSS_ACADEMY_ONLY` unless they are both constraint-aware and gated by enough safe novelty headroom.

## Bottom Line

This engine has a strong product idea but a weak scheduling core.

The most important combined conclusion from both critiques is:

1. round legality is not guaranteed
2. category semantics are not trustworthy
3. phase selection is structurally brittle
4. inter-academy strategy promises are not enforced
5. scheduling architecture is incomplete for production use

That combination means the next implementation pass should focus less on clever heuristics and more on explicit constraints, invariants, and truthful strategy contracts.
