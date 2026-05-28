# Fixture Engine — Phased Implementation Plan

## Status (2026-05-28)

| Phase | Status | Notes |
|---|---|---|
| Phase 1 — Invariant tests + fixture corpus | ✅ Landed | 20 invariant tests pinning critique items |
| Phase 2 — Correctness fixes + additive slot model + schema migration | ✅ Landed | Transition legality, additive fields, OUT_OF_BAND labeling, singleton-tier absorption, scan short-circuit, design alignment |
| Phase 3 — Multi-wave scheduler + capacity field rename | ✅ Landed | `session_scheduler.py`, numeric `wave_number`, `matches_per_player_estimate` |
| Phase 4 — Pairing solver + rematch policy | ✅ Landed | `pairing_solver.py` + `rematch_policy.py`, networkx dep, migrated leftover + stretch fallback paths |
| Phase 5 — Config layer + regime + robust phase detection | ✅ Landed | `fixture_config.py` + `rating_regime.py`, P90-P10 + provisional-majority `detect_phase` |
| Phase 6 — Pre-flight feasibility warnings + frontend surface | ✅ Landed | `fixture_preflight.py`, inline warning rendering in `EventDetailPanel.tsx` |
| Phase 7 — Docs + critique annotations + design fixes | ✅ Landed | This doc, critique markers, API contract deprecation note, design-doc math fix |

Final test counts: **265 backend tests passing, 25 skipped**, TypeScript builds clean.

## Purpose

This plan addresses every issue raised in [fixture_engine_best_of_both_critique.md](/c:/rallypoint/docs/fixture_engine_best_of_both_critique.md) for [app/services/fixture_engine.py](/c:/rallypoint/app/services/fixture_engine.py).

**Decisions locked in before drafting:**

- **Scope:** Full redesign — all 22 critique items.
- **`match_category` migration:** Additive — new richer fields written alongside a compatibility `match_category`. Downstream consumers ([match_service.py](/c:/rallypoint/app/services/match_service.py), [player_service.py](/c:/rallypoint/app/services/player_service.py)) migrate later.
- **Inter-academy pairing vs scheduling:** Split done alongside correctness fixes, not deferred.
- **Tests:** Extend the existing [tests/unit/test_fixture_engine.py](/c:/rallypoint/tests/unit/test_fixture_engine.py).
- **Solver library:** `networkx` allowed for `max_weight_matching`.
- **Config storage:** New keys in the existing `system_configuration` table ([sql/system_configuration.sql](/c:/rallypoint/sql/system_configuration.sql)), accessed via the existing config router pattern. A thin `app/services/fixture_config.py` module loads, caches, and exposes typed accessors for fixture-specific keys — it does not store the config itself.
- **`recent_match_counts`:** `fixture_engine.py` keeps zero DB access. The caller (event/fixture router) loads recent match counts from the DB and passes them in as a parameter.
- **Warnings UX:** Reuse the existing inline error pattern in [web/src/components/EventDetailPanel.tsx](/c:/rallypoint/web/src/components/EventDetailPanel.tsx) (`genError` + `ErrorMsg`). Extend it to support a `warnings: string[]` field on the fixture-generation response and render alongside `genError` — no new screen needed.

## Phase 1 — Invariants, Contract Tests, Shared Fixtures

**Goal:** Lock down expected behavior with failing tests before changing engine code.

**New tests added to [tests/unit/test_fixture_engine.py](/c:/rallypoint/tests/unit/test_fixture_engine.py):**

- `test_no_duplicate_player_in_round` — every player appears at most once per `(round_number, sub_round)`.
- `test_attending_player_covered` — every attending player appears exactly once per round as a match participant or BYE.
- `test_cross_academy_only_invariant` — `academy_a != academy_b` on every non-BYE slot.
- `test_tier_matched_no_same_academy` — when ≥2 academies are present in a tier, no same-academy pairs unless fallback mode is explicitly flagged.
- `test_singleton_tier_never_disappears` — a tier of size 1 always produces a slot.
- `test_round_offset_honored_every_phase` — DISCOVERY, TRANSITION, STANDARD all respect `round_offset`.
- `test_multi_wave_unique_numbering` — 3+ waves produce distinct wave numbers.
- `test_out_of_band_surfaced_explicitly` — pairings outside stretch threshold are labeled, not hidden inside STRETCH/COMPETITIVE.
- `test_rematch_preference_when_alternatives_exist` — non-rematch chosen over recent rematch when both legal.

**Fixture corpus added to [tests/conftest.py](/c:/rallypoint/tests/conftest.py):**

- `flat_pool_16` (DISCOVERY), `mixed_pool_24` (TRANSITION), `wide_pool_32` (STANDARD).
- `dominant_academy_pool` (4:1 skew), `singleton_tier_pool`, `odd_size_tier_pool`.
- `provisional_heavy_pool`, `elite_pool`.

**Exit criterion:** all new tests fail meaningfully against current code.

## Phase 2 — Correctness Bugs (Legality Floor)

**Critique items addressed:** #1, #2, #3, #6, #10, #18, #19, #20.

### 2a. Transition round legality (#1)

Replace [within_half_pairs()](/c:/rallypoint/app/services/fixture_engine.py:250) and [cross_pairs()](/c:/rallypoint/app/services/fixture_engine.py:272) with a true one-match-per-player round-robin within each half (circle method). For odd total counts in cross-half rounds, emit an explicit BYE.

### 2b. Additive category model (#2)

Add to every slot dict:

- `round_intent`: `COMPETITIVE` | `DEVELOPMENTAL`
- `gap_band`: `COMPETITIVE` | `STRETCH` | `OUT_OF_BAND` | `BYE`
- `player_a_role`, `player_b_role`: `PEER` | `STRETCHING` | `ANCHORING` | `BYE`

Continue writing `match_category` as a derived compatibility field. Emit `ANCHOR` correctly per design. No changes to match_service / player_service in this phase.

### 2c. Standard-phase leftover handling (#3)

Move leftover and odd-tier handling into a single constrained pairing pass:

1. Try same-tier pairing.
2. Try adjacent-tier fallback within configured gap.
3. If still isolated, allow an explicitly labeled `OUT_OF_BAND` exception within `max_exception_gap`.
4. BYE only as last resort.

Guardrails: `max_consecutive_byes_for_same_reason`, `max_exception_gap`. `max_exception_gap` must stay ≤ the existing rating-eligible cap of 500 enforced in [match_service.py](/c:/rallypoint/app/services/match_service.py:60).

### 2d. Singleton-tier policy (#6)

In `_tier_matched()`, detect tier of size 1 and run the same-tier → adjacent-tier → labeled exception → BYE ladder. Never silent-drop.

### 2e. `stretch_pairs()` monotonic scan (#10)

Short-circuit the descending scan in [stretch_pairs()](/c:/rallypoint/app/services/fixture_engine.py:389) when `gap > _STRETCH_MAX`. Replace greedy scan with bounded candidate generation.

### 2f. Design vs code mismatches (#18, #19, #20)

- Align [detect_phase()](/c:/rallypoint/app/services/fixture_engine.py:33) boundary operators with the design: `<= 100` (discovery), `> 250` (standard).
- Route `<6` player sessions through pure round-robin per [jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design:340).
- Deterministic ordering (by `player_id`) in [_circle_round()](/c:/rallypoint/app/services/fixture_engine.py:168).

**Exit criterion:** Phase 1 legality and contract tests pass. Downstream `match_category` consumers untouched.

## Phase 3 — Strategy Contracts + Scheduler Split

**Critique items addressed:** #4, #5, #11, #12, #13, plus the pairing-vs-scheduling split.

### 3a. `CROSS_ACADEMY_ONLY` (#4)

Build a legal cross-academy base schedule first. Make novelty swapping in [_swap_for_novelty()](/c:/rallypoint/app/services/fixture_engine.py:588) optional, constraint-aware, and gated by headroom (count of remaining cross-academy non-rematch opponents per player + academy-skew signal). Skip the novelty pass entirely in saturated or dominant-academy pools.

### 3b. `TIER_MATCHED` (#5)

Replace plain round-robin inside each tier with constrained matching that forbids same-academy edges when ≥2 academies are present. Surface fallback mode explicitly in slot output when the constraint is relaxed.

### 3c. Multi-wave scheduling (#11)

Replace `sub_round: "A" | "B"` with numeric `wave_number`. Update [_assign_tables()](/c:/rallypoint/app/services/fixture_engine.py:125) and [_assign_tables_league()](/c:/rallypoint/app/services/fixture_engine.py:622) to handle N waves. Derive display label `A/B/C/...` from the numeric value if needed.

### 3d. `round_offset` consistency (#12)

Add `round_offset` to the interface of every phase generator (discovery, transition, standard).

### 3e. `matches_per_player` truthfulness (#13)

Rename to `matches_per_player_estimate` in the return contract of [calculate_session_capacity()](/c:/rallypoint/app/services/fixture_engine.py:59). Document that actual count may differ.

### 3f. Inter-academy pairing-vs-scheduling split

New module `app/services/session_scheduler.py`:

- Input: pairing list, table count, wave duration, session minutes.
- Output: executable waves with table assignments.

Refactor `_cross_academy_only`, `_team_format`, `_tier_matched`, full-round-robin to return pure pairing matrices and route through the scheduler. Intra-academy phases also route through the scheduler so multi-wave numbering and table contention share one model.

**Exit criterion:** Strategy-contract tests pass. Inter-academy outputs are executable schedules.

## Phase 4 — Constrained-Matching Solver (New Pairing Core)

**Critique items addressed:** #9, #17, plus foundation for #14 fairness frames.

### 4a. Solver skeleton

New module `app/services/pairing_solver.py`:

1. Build candidate edges respecting hard constraints.
2. Score each edge with a soft cost function.
3. Run min-cost matching via `networkx.max_weight_matching`.
4. Return matching + unmatched players (BYE candidates).

### 4b. Hard constraints

- One match per player per round.
- Academy restrictions per strategy.
- Wave / table capacity limits.
- Gap caps per regime (populated in Phase 5).

### 4c. Soft scoring (config-driven weights)

- Distance from target gap.
- Same-tier / adjacent-tier preference.
- Rematch penalty (harm formula from #17).
- BYE-balance penalty.
- Developmental-exposure balance.
- Isolation-exception penalty.

### 4d. Rematch policy layer (#17)

New module `app/services/rematch_policy.py`:

- Receives `recent_match_counts[(a, b)]` and `recent_match_window_days` as caller-supplied input. The fixture engine keeps zero DB access.
- The fixture/event router (caller) loads recent matches from the DB and passes them in.
- Harm score factors: recency, repeat count, same-session, context repetition, gap quality, BYE-relief credit.
- Phase/strategy-specific weights:
  - `DISCOVERY`: strongest preference for fresh opponents.
  - `TRANSITION` / `STANDARD`: standard penalty.
  - `CROSS_ACADEMY_ONLY`: drives the gated novelty pass from 3a.
  - `TEAM_FORMAT`: weaker (positional constraint dominates).
- Hard cap (e.g., `max_recent_matches_same_pair`) as a constraint, not just a penalty.
- Complement, not replacement, of the existing `diminishing_signal_applied` damping in [match_service.py](/c:/rallypoint/app/services/match_service.py:60).

### 4e. Migrate each generator to call the solver

- `discovery` (mostly round-robin; solver used for last-round leftovers).
- `transition` (replaces the buggy half-split).
- `standard` (replaces tiered leftover handling).
- Inter-academy strategies (solver enforces academy constraints).

**Caller wiring:** the fixture router that invokes `generate_fixtures()` is responsible for querying recent matches and passing `recent_match_counts` plus the configured window into the engine.

**Exit criterion:** all pairing decisions flow through the solver. Phase 1 invariants still pass.

## Phase 5 — Phase Detection + Threshold Config (Regime Layer)

**Critique items addressed:** #7, #8, #9.

### 5a. Config storage and access

- New rows added to the existing `system_configuration` table via a new SQL migration ([sql/system_configuration.sql](/c:/rallypoint/sql/system_configuration.sql) pattern). Example keys:
  - `fixture.regime.developing.competitive_max_gap`
  - `fixture.regime.elite_proximity.stretch_max_gap`
  - `fixture.rematch.max_recent_matches_same_pair`
  - `fixture.phase.discovery_core_spread_threshold`
- New `app/services/fixture_config.py` module: loads fixture-prefixed keys via the same connection pattern used in [app/routers/config.py](/c:/rallypoint/app/routers/config.py), caches them, and exposes typed accessors (e.g., `get_regime_thresholds(regime)`).
- Single config source consumed by phase gating, tier grouping, gap classification, fallback policy, rematch policy.

### 5b. Robust phase detection (#7)

Replace raw `max - min` spread in [detect_phase()](/c:/rallypoint/app/services/fixture_engine.py:33) with:

- `core_spread = P90 - P10` of ratings.
- Tier occupancy counts.
- Provisional / low-confidence player count (reuse `total_matches = rated_matches_completed + virtual_matches` from rating services).
- Count of eligible competitive neighbors and developmental partners.

Gating logic per the critique's DISCOVERY / TRANSITION / STANDARD recipe.

### 5c. Engine-facing regime layer (#8)

New module `app/services/rating_regime.py` with regimes `VOLATILE_LOW`, `DEVELOPING`, `HIGH_LEVEL`, `ELITE_PROXIMITY`.

- Inputs: absolute rating + maturity (`total_matches`, confidence ratio, provisional flag) — reusing existing rating signals, no duplication.
- Outputs: calibrated thresholds for the solver.
- Visible program tiers (`BEGINNER` / `INTERMEDIATE` / `ADVANCED` / `ELITE` / `NATIONAL_TRACK`) stay untouched — regime is engine-internal.
- `ELITE_PROXIMITY` uses a hybrid trigger: absolute threshold OR top-percentile OR `NATIONAL_TRACK` + confidence.

### 5d. Tier / fairness width alignment (#9)

Tier-aware competitive and stretch caps (e.g., elite tier uses narrower gap than developing tier). Document tiers as a coarse grouping mechanism, not the final fairness mechanism.

**Exit criterion:** all thresholds configurable via `system_configuration`. No hardcoded numbers in pairing code. Phase detection robust against single outliers.

## Phase 6 — Fairness Frames, Pre-Flight Warnings, Design Alignment

**Critique items addressed:** #14 (A/B/C/D), #15, #16, #21, #22.

### 6a. Pre-flight feasibility checks

New module `app/services/fixture_preflight.py`. Returns a `warnings: list[dict]` with code + human-readable message before fixture generation:

- `dominant_academy_bye_burden` — `CROSS_ACADEMY_ONLY` with one academy ≥ X% of pool.
- `team_format_lineup_imbalance` — `TEAM_FORMAT` with materially different roster sizes.
- `odd_tier_island` — isolated odd-size tiers with no merge candidate.
- `tier_capacity_skew` — tier-vs-table mismatch forcing many waves for one tier.

Operator can proceed, downgrade strategy, or adjust roster.

### 6b. CROSS_ACADEMY_ONLY sit-out spikes (#15)

Use preflight to recommend strategy downgrade in heavily skewed pools.

### 6c. Odd-number islands (#16)

Adjacent-tier merge inside gap cap. Surface expected BYE burden in preflight when no merge available.

### 6d. TEAM_FORMAT documentation (#14B)

Update [docs/jlrs_fixtures_design](/c:/rallypoint/docs/jlrs_fixtures_design) to state rank-position pairing creates BYEs in uneven rosters. Optionally add `TEAM_FORMAT_ROTATING` lineup policy stub for future iteration.

### 6e. Design doc fixes (#21, #22)

- Add a Swiss-style monthly meet stub or document deferral.
- Fix the `10 academies × 4 players` example: 45 pairings × 4 = 180 matches.

### 6f. Front-end warning surfacing

Backend changes:

- Fixture-generation endpoint response gains a `warnings: string[]` field (or `warnings: { code, message }[]`).

Frontend changes in [web/src/components/EventDetailPanel.tsx](/c:/rallypoint/web/src/components/EventDetailPanel.tsx):

- Add `genWarnings: string[]` alongside the existing `genError` state.
- Render warnings using the existing `ErrorMsg` component styling (or a sibling `WarningMsg` variant in [web/src/components/Layout.tsx](/c:/rallypoint/web/src/components/Layout.tsx)).
- No new screen needed — the inline pattern already used for errors covers this.
- Update fixture-related types in [web/src/types](/c:/rallypoint/web/src/types) (or wherever `EventFixtures` is defined) to include the new field.

**Exit criterion:** operators see actionable warnings before publishing problematic fixtures. Design doc is internally consistent.

## Phase 7 — Cleanup, Documentation, Downstream Migration Prep

### 7a. Documentation

- Mark each item in [docs/jlrs_fixture_engine_critique.md](/c:/rallypoint/docs/jlrs_fixture_engine_critique.md) and [docs/fixture_engine_best_of_both_critique.md](/c:/rallypoint/docs/fixture_engine_best_of_both_critique.md) as addressed.
- Add a fixture_engine module docstring describing the new solver-based architecture.

### 7b. Migration runway for `match_category`

- Document the additive fields in [docs/jlrs_api_contract.md](/c:/rallypoint/docs/jlrs_api_contract.md).
- Add a deprecation note on `match_category`.
- Provide a query example showing how match_service / player_service can transition to the richer fields.

### 7c. Performance check

Benchmark solver on the largest expected pool size. Confirm no regression vs current naive matching.

**Exit criterion:** all 22 items closed. Downstream services have a clear migration path. Design doc is accurate.

## Cross-Cutting Commitments

- **Zero DB access in `fixture_engine.py`:** preserved. All DB-derived inputs (`recent_match_counts`, regime config) are loaded by the caller and passed in.
- **Hard cap from existing services preserved:** the `> 500` rating-eligible cap in match_service is the ceiling for `max_exception_gap`. `diminishing_signal_applied` stays — fixture-time rematch policy complements it.
- **Backward compatibility:** `match_category` always written until Phase 7 documents retirement.
- **Visible tiers untouched:** product-facing tier taxonomy preserved; regime layer is engine-internal.
- **Test discipline:** every phase ends with the Phase 1 invariant suite still green plus new tests for that phase's behavior.

## Critique Item Coverage Matrix

| # | Critique Item | Phase |
|---|---|---|
| 1 | Transition phase legality | 2a |
| 2 | Match category semantics | 2b |
| 3 | Standard-phase extreme leftovers | 2c |
| 4 | CROSS_ACADEMY_ONLY contract break | 3a |
| 5 | TIER_MATCHED not enforced | 3b |
| 6 | Singleton tier disappearance | 2d |
| 7 | detect_phase brittleness | 5b |
| 8 | Hardcoded scaling thresholds | 5a, 5c |
| 9 | Tier vs fairness width misalignment | 5d |
| 10 | stretch_pairs greedy scan | 2e |
| 11 | _assign_tables only handles two waves | 3c |
| 12 | round_offset inconsistency | 3d |
| 13 | matches_per_player not guaranteed | 3e |
| 14A | CROSS_ACADEMY_ONLY teammate spikes | 6a, 6b |
| 14B | TEAM_FORMAT lineup bottlenecks | 6a, 6d |
| 14C | TIER_MATCHED odd-number islands | 6a, 6c |
| 14D | TIER_MATCHED infrastructure starvation | 6a |
| 15 | CROSS_ACADEMY_ONLY sit-out spikes | 6b |
| 16 | Odd-number islands | 6c |
| 17 | Rematch control weak | 4d |
| 18 | Phase boundary operator mismatch | 2f |
| 19 | Small-session fallback mismatch | 2f |
| 20 | Discovery ordering not normalized | 2f |
| 21 | Swiss-like cross-academy missing | 6e |
| 22 | TEAM_FORMAT design example wrong | 6e |
| Inter-academy split | Pairing matrix vs schedule | 3f |
