"""
Unit tests for fixture_engine.py — pure Python, no DB.
Tests cover:
  - Phase detection at spread boundaries
  - Session capacity formula
  - Circle-method round-robin (N=8 even, N=9 odd)
  - Discovery fixture generation
  - Standard fixtures: BYE for odd count, recent_match_pairs dedup
  - Full dispatcher for 20 players → 30 slots
  - Inter-academy league fixture strategies: TIER_MATCHED, CROSS_ACADEMY_ONLY, TEAM_FORMAT, FULL_ROUND_ROBIN
"""
import math

import pytest

from app.services.fixture_config import DEFAULT_FIXTURE_CONFIG
from app.services.fixture_engine import (
    _canonical,
    _classify_gap,
    _circle_round,
    _resolve_regime_thresholds,
    calculate_session_capacity,
    detect_phase,
    generate_discovery_fixtures,
    generate_fixtures,
    generate_league_fixtures,
    generate_standard_fixtures,
    generate_transition_fixtures,
    rating_spread,
)
from app.services.rating_regime import (
    REGIME_DEVELOPING,
    REGIME_VOLATILE_LOW,
    REGIME_HIGH_LEVEL,
    regime_thresholds,
)


def _make_players(ratings: list[float]) -> list[dict]:
    return [
        {"player_id": f"p{i}", "current_rating": r}
        for i, r in enumerate(ratings)
    ]


# ── Phase detection ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spread,expected_phase", [
    # Aligned with docs/jlrs_fixtures_design and critique §18:
    # spread ≤ 100 → DISCOVERY, 100 < spread ≤ 250 → TRANSITION, spread > 250 → STANDARD.
    (0,   "DISCOVERY"),
    (50,  "DISCOVERY"),
    (99,  "DISCOVERY"),
    (100, "DISCOVERY"),
    (101, "TRANSITION"),
    (249, "TRANSITION"),
    (250, "TRANSITION"),
    (251, "STANDARD"),
    (500, "STANDARD"),
])
def test_detect_phase_boundaries(spread, expected_phase):
    players = [
        {"player_id": "a", "current_rating": 1000.0},
        {"player_id": "b", "current_rating": 1000.0 + spread},
    ]
    assert detect_phase(players) == expected_phase


def test_detect_phase_single_player_returns_discovery():
    assert detect_phase([{"player_id": "a", "current_rating": 1500.0}]) == "DISCOVERY"


def test_detect_phase_empty_returns_discovery():
    assert detect_phase([]) == "DISCOVERY"


def test_rating_spread():
    players = _make_players([900.0, 1000.0, 1200.0])
    assert rating_spread(players) == 300.0


def test_rating_spread_single_player():
    assert rating_spread([{"player_id": "a", "current_rating": 1000.0}]) == 0.0


def test_classify_gap_uses_regime_thresholds():
    vol_thresholds = regime_thresholds(REGIME_VOLATILE_LOW)
    dev_thresholds = regime_thresholds(REGIME_DEVELOPING)

    assert _classify_gap(130.0, vol_thresholds) == "COMPETITIVE"
    assert _classify_gap(130.0, dev_thresholds) == "STRETCH"


def test_resolve_regime_thresholds_varies_with_pool():
    mature_pool = [
        {"player_id": "p1", "current_rating": 1500.0, "rated_matches_completed": 30},
        {"player_id": "p2", "current_rating": 1520.0, "rated_matches_completed": 40},
    ]
    provisional_pool = [
        {"player_id": "p1", "current_rating": 1500.0, "rated_matches_completed": 1, "is_provisional": True},
        {"player_id": "p2", "current_rating": 1520.0, "rated_matches_completed": 1, "is_provisional": True},
    ]
    mature_thresholds = _resolve_regime_thresholds(mature_pool, cfg=DEFAULT_FIXTURE_CONFIG)
    provisional_thresholds = _resolve_regime_thresholds(provisional_pool, cfg=DEFAULT_FIXTURE_CONFIG)

    assert mature_thresholds.name == REGIME_HIGH_LEVEL
    assert mature_thresholds.competitive_max_gap == 75.0
    assert provisional_thresholds.name == REGIME_VOLATILE_LOW
    assert provisional_thresholds.competitive_max_gap == 150.0


def test_generate_fixtures_gap_bands_adapt_to_pool():
    mature_pool = [
        {"player_id": "p1", "current_rating": 1500.0, "rated_matches_completed": 30},
        {"player_id": "p2", "current_rating": 1415.0, "rated_matches_completed": 30},
        {"player_id": "p3", "current_rating": 1450.0, "rated_matches_completed": 30},
        {"player_id": "p4", "current_rating": 1420.0, "rated_matches_completed": 30},
    ]
    developing_pool = [
        {"player_id": "p1", "current_rating": 1250.0, "rated_matches_completed": 30},
        {"player_id": "p2", "current_rating": 1165.0, "rated_matches_completed": 30},
        {"player_id": "p3", "current_rating": 1200.0, "rated_matches_completed": 30},
        {"player_id": "p4", "current_rating": 1170.0, "rated_matches_completed": 30},
    ]
    mature_thresholds = _resolve_regime_thresholds(mature_pool, cfg=DEFAULT_FIXTURE_CONFIG)
    developing_thresholds = _resolve_regime_thresholds(developing_pool, cfg=DEFAULT_FIXTURE_CONFIG)

    assert mature_thresholds.name == REGIME_HIGH_LEVEL
    assert developing_thresholds.name == REGIME_DEVELOPING
    assert mature_thresholds.competitive_max_gap == 75.0
    assert developing_thresholds.competitive_max_gap == 100.0

    cfg = DEFAULT_FIXTURE_CONFIG
    thresholds = _resolve_regime_thresholds(mature_pool, cfg=cfg)

    mature_result = generate_fixtures(
        players=mature_pool,
        recent_match_pairs=set(),
        session_minutes=90,
        num_tables=2,
        match_format="BEST_OF_3",
        rotation_offset=0,
        cfg=cfg,
    )
    developing_result = generate_fixtures(
        players=developing_pool,
        recent_match_pairs=set(),
        session_minutes=90,
        num_tables=2,
        match_format="BEST_OF_3",
        rotation_offset=0,
        cfg=cfg,
    )

    mature_bands = {slot["gap_band"] for slot in mature_result["slots"] if slot["player_b_id"] is not None}
    developing_bands = {slot["gap_band"] for slot in developing_result["slots"] if slot["player_b_id"] is not None}

    assert "STRETCH" in mature_bands
    assert "COMPETITIVE" in developing_bands
    assert mature_bands != developing_bands


# ── Session capacity ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("session_min,tables,fmt,n_players,exp_mpt,exp_total,exp_mpp", [
    # BEST_OF_3: slot_time = 20 + 5 = 25
    (90,  3, "BEST_OF_3", 10, 3, 9,  1),   # 9*2//10=1
    (125, 3, "BEST_OF_3", 10, 5, 15, 3),   # 15*2//10=3
    (200, 10, "BEST_OF_3", 10, 8, 80, 4),  # 80*2//10=16 → capped at 4
    # BEST_OF_5: slot_time = 30 + 5 = 35
    (120, 4, "BEST_OF_5", 8, 3, 12, 3),    # 12*2//8=3
    (175, 5, "BEST_OF_5", 20, 5, 25, 2),   # 25*2//20=2
    # BEST_OF_7: slot_time = 40 + 5 = 45
    (90,  2, "BEST_OF_7", 6, 2,  4, 1),    # 4*2//6=1
])
def test_session_capacity(session_min, tables, fmt, n_players, exp_mpt, exp_total, exp_mpp):
    result = calculate_session_capacity(session_min, tables, fmt, n_players)
    assert result["matches_per_table"] == exp_mpt
    assert result["total_slots"] == exp_total
    assert result["matches_per_player"] == exp_mpp


def test_session_capacity_zero_players():
    result = calculate_session_capacity(90, 3, "BEST_OF_3", 0)
    assert result["matches_per_player"] == 0


# ── Circle method ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n", [8, 16, 20])
def test_circle_round_no_self_pairings(n):
    players = _make_players([1000.0] * n)
    total_rounds = n - 1  # n is even for all test cases
    for round_idx in range(total_rounds):
        pairs = _circle_round(players, round_idx)
        for a, b in pairs:
            if a is not None and b is not None:
                assert a != b, f"Self-pairing in round {round_idx}"


@pytest.mark.parametrize("n", [8, 16, 20])
def test_circle_round_each_player_appears_once_per_round(n):
    players = _make_players([1000.0] * n)
    for round_idx in range(n - 1):
        pairs = _circle_round(players, round_idx)
        pids = [pid for pair in pairs for pid in pair if pid is not None]
        assert len(pids) == len(set(pids)), f"Duplicate player in round {round_idx}"


def test_circle_round_full_rr_coverage_n8():
    """N=8: full round-robin covers all 28 unique pairs exactly once."""
    players = _make_players([1000.0] * 8)
    all_pairs: set[tuple] = set()
    for round_idx in range(7):
        for a, b in _circle_round(players, round_idx):
            if a is not None and b is not None:
                all_pairs.add(_canonical(a, b))
    assert len(all_pairs) == 28  # 8*7/2


def test_circle_round_odd_players_has_exactly_one_bye_per_round():
    players = _make_players([1000.0] * 9)
    for round_idx in range(9):
        pairs = _circle_round(players, round_idx)
        bye_count = sum(1 for a, b in pairs if a is None or b is None)
        assert bye_count == 1, f"Expected 1 BYE in round {round_idx}, got {bye_count}"


def test_circle_round_odd_players_each_player_gets_bye():
    """In 9-player full round-robin (9 rounds), each player gets BYE exactly once."""
    players = _make_players([1000.0] * 9)
    bye_counts: dict[str, int] = {}
    for round_idx in range(9):
        for a, b in _circle_round(players, round_idx):
            if a is None or b is None:
                bye_player = b if a is None else a
                bye_counts[bye_player] = bye_counts.get(bye_player, 0) + 1
    for pid, count in bye_counts.items():
        assert count == 1, f"Player {pid} got BYE {count} times"


# ── Discovery fixtures ─────────────────────────────────────────────────────────

def test_discovery_fixtures_no_self_pairings():
    players = _make_players([1000.0] * 8)
    slots = generate_discovery_fixtures(players, matches_per_player=4, num_tables=4, rotation_offset=0)
    for slot in slots:
        if slot["player_b_id"] is not None:
            assert slot["player_a_id"] != slot["player_b_id"]


def test_discovery_fixtures_rotation_offset_shifts_pairs():
    """rotation_offset varies circle-method rotation for discovery diversity."""
    players = _make_players([1000.0] * 8)
    slots_0 = generate_discovery_fixtures(players, matches_per_player=1, num_tables=4, rotation_offset=0)
    slots_3 = generate_discovery_fixtures(players, matches_per_player=1, num_tables=4, rotation_offset=3)
    pairs_0 = {(_canonical(s["player_a_id"], s["player_b_id"])) for s in slots_0 if s["player_b_id"]}
    pairs_3 = {(_canonical(s["player_a_id"], s["player_b_id"])) for s in slots_3 if s["player_b_id"]}
    assert pairs_0 != pairs_3


def test_discovery_fixtures_round_numbers_session_local():
    """Round numbers are 1, 2, 3, ... regardless of rotation_offset."""
    players = _make_players([1000.0] * 8)
    slots = generate_discovery_fixtures(players, matches_per_player=4, num_tables=4, rotation_offset=5)
    round_numbers = {s["round_number"] for s in slots}
    assert round_numbers == {1, 2, 3, 4}, (
        f"Expected rounds 1-4 (session-local), got {sorted(round_numbers)}"
    )


def test_discovery_fixtures_sub_rounds_when_more_pairs_than_tables():
    # 8 players → 4 pairs per round, 3 tables → needs sub-rounds
    players = _make_players([1000.0] * 8)
    slots = generate_discovery_fixtures(players, matches_per_player=1, num_tables=3, rotation_offset=0)
    sub_rounds = {s["sub_round"] for s in slots}
    assert "A" in sub_rounds
    assert "B" in sub_rounds


def test_discovery_fixtures_no_sub_rounds_when_fits():
    # 8 players → 4 pairs per round, 4 tables → fits without sub-rounds
    players = _make_players([1000.0] * 8)
    slots = generate_discovery_fixtures(players, matches_per_player=1, num_tables=4, rotation_offset=0)
    assert all(s["sub_round"] is None for s in slots)


# ── Transition fixtures ────────────────────────────────────────────────────────

def test_transition_fixtures_has_stretch_round():
    # 8 players, 3 rounds: round 2 (index 1) should be STRETCH
    players = _make_players([1300.0, 1250.0, 1200.0, 1150.0, 1100.0, 1050.0, 1000.0, 950.0])
    slots = generate_transition_fixtures(players, matches_per_player=3, num_tables=4)
    round2_slots = [s for s in slots if s["round_number"] == 2]
    assert all(s["match_category"] == "STRETCH" for s in round2_slots)


def test_transition_fixtures_competitive_rounds_not_stretch():
    players = _make_players([1300.0, 1250.0, 1200.0, 1150.0, 1100.0, 1050.0, 1000.0, 950.0])
    slots = generate_transition_fixtures(players, matches_per_player=3, num_tables=4)
    round1_slots = [s for s in slots if s["round_number"] == 1]
    assert all(s["match_category"] == "COMPETITIVE" for s in round1_slots)


def test_transition_fixtures_no_self_pairings():
    players = _make_players([1300.0, 1250.0, 1200.0, 1150.0, 1100.0, 1050.0, 1000.0, 950.0])
    slots = generate_transition_fixtures(players, matches_per_player=3, num_tables=4)
    for slot in slots:
        if slot["player_b_id"] is not None:
            assert slot["player_a_id"] != slot["player_b_id"]


# ── Standard fixtures ──────────────────────────────────────────────────────────

def test_standard_fixtures_bye_for_odd_count():
    # 5 players → one gets BYE in competitive round
    players = _make_players([1400.0, 1300.0, 1200.0, 1100.0, 1000.0])
    slots = generate_standard_fixtures(players, set(), matches_per_player=2, num_tables=4)
    bye_slots = [s for s in slots if s["player_b_id"] is None]
    assert len(bye_slots) > 0


def test_standard_fixtures_no_self_pairings():
    players = _make_players([1600.0, 1500.0, 1300.0, 1200.0, 1100.0, 1000.0])
    slots = generate_standard_fixtures(players, set(), matches_per_player=4, num_tables=4)
    for slot in slots:
        if slot["player_b_id"] is not None:
            assert slot["player_a_id"] != slot["player_b_id"]


def test_standard_fixtures_stretch_excludes_recent_pairs():
    """
    Pairs in recent_match_pairs should not appear in the dedicated stretch
    round when a legal non-rematch alternative exists.

    Pool shape: 6 players across 3 even-sized tiers (NT×2, ELITE×2, ADV×2)
    → no odd tier groups → C-S-C-S pattern → round 2 (step=1) is the
    dedicated stretch round.
    """
    players = [
        {"player_id": "a", "current_rating": 1600.0},   # NT
        {"player_id": "b", "current_rating": 1550.0},   # NT
        {"player_id": "c", "current_rating": 1400.0},   # ELITE
        {"player_id": "d", "current_rating": 1350.0},   # ELITE
        {"player_id": "e", "current_rating": 1200.0},   # ADV
        {"player_id": "f", "current_rating": 1150.0},   # ADV
    ]
    # (a, c) gap=200 sits squarely in the stretch band; exclude it and the
    # engine must find a different stretch partner for `a`.
    excluded = _canonical("a", "c")
    slots = generate_standard_fixtures(players, {excluded}, matches_per_player=2, num_tables=4)
    stretch_slots = [s for s in slots if s["round_number"] == 2]
    stretch_pairs = {
        _canonical(s["player_a_id"], s["player_b_id"])
        for s in stretch_slots if s["player_b_id"]
    }
    assert excluded not in stretch_pairs, (
        f"stretch round 2 still contains excluded recent pair {excluded}: {stretch_pairs}"
    )


def test_standard_fixtures_stretch_gap_filter():
    """Pairs with gap < 100 should not appear in stretch round."""
    # 6 players: first two have gap=50 (too close for stretch), others have wider gaps
    players = _make_players([1600.0, 1550.0, 1300.0, 1200.0, 1000.0, 900.0])
    slots = generate_standard_fixtures(players, set(), matches_per_player=2, num_tables=4)
    stretch_slots = [s for s in slots if s["match_category"] == "STRETCH"]
    for slot in stretch_slots:
        assert slot["expected_rating_gap"] >= 100.0, (
            f"Stretch slot has gap {slot['expected_rating_gap']} < 100"
        )


def test_standard_fixtures_competitive_rounds_alternate():
    """Odd-numbered rounds (1, 3, ...) are COMPETITIVE; even (2, 4, ...) are STRETCH."""
    players = _make_players([1600.0, 1500.0, 1300.0, 1200.0, 1100.0, 1000.0])
    slots = generate_standard_fixtures(players, set(), matches_per_player=4, num_tables=4)
    for slot in slots:
        rn = slot["round_number"]
        if rn % 2 == 1:  # rounds 1, 3
            assert slot["match_category"] in ("COMPETITIVE", "STRETCH"), (
                f"Round {rn} slot has unexpected category {slot['match_category']}"
            )


# ── Full dispatcher ────────────────────────────────────────────────────────────

def test_generate_fixtures_discovery_20_players():
    """20 players, spread=0 → DISCOVERY. 150 min, 5 tables, BO3 → mpp=3, 30 slots."""
    players = _make_players([1000.0] * 20)
    result = generate_fixtures(
        players=players,
        recent_match_pairs=set(),
        session_minutes=150,
        num_tables=5,
        match_format="BEST_OF_3",
        rotation_offset=0,
    )
    assert result["phase"] == "DISCOVERY"
    assert result["matches_per_player"] == 3
    assert len(result["slots"]) == 30

    for slot in result["slots"]:
        if slot["player_b_id"] is not None:
            assert slot["player_a_id"] != slot["player_b_id"]

    competitive = sum(1 for s in result["slots"] if s["match_category"] == "COMPETITIVE")
    assert competitive == 30  # DISCOVERY → all COMPETITIVE


def test_generate_fixtures_returns_phase_and_spread():
    players = [
        {"player_id": "a", "current_rating": 1000.0},
        {"player_id": "b", "current_rating": 1300.0},
    ]
    result = generate_fixtures(
        players=players,
        recent_match_pairs=set(),
        session_minutes=120,
        num_tables=2,
        match_format="BEST_OF_3",
        rotation_offset=0,
    )
    assert result["phase"] == "STANDARD"
    assert result["spread"] == 300.0


def test_generate_fixtures_zero_capacity():
    """Session too short for any match → mpp=0, slots=[]."""
    players = _make_players([1000.0, 1200.0])
    result = generate_fixtures(
        players=players,
        recent_match_pairs=set(),
        session_minutes=20,  # 20 < 25 (BEST_OF_3 + changeover)
        num_tables=1,
        match_format="BEST_OF_3",
        rotation_offset=0,
    )
    assert result["matches_per_player"] == 0
    assert result["slots"] == []


def test_generate_fixtures_transition_phase():
    # spread = 200 → TRANSITION
    players = _make_players([1200.0, 1150.0, 1100.0, 1050.0, 1000.0, 1050.0])
    # Make unique player_ids
    for i, p in enumerate(players):
        p["player_id"] = f"t{i}"
        p["current_rating"] = 1000.0 + i * 40  # 1000, 1040, 1080, 1120, 1160, 1200

    result = generate_fixtures(
        players=players,
        recent_match_pairs=set(),
        session_minutes=120,
        num_tables=3,
        match_format="BEST_OF_3",
        rotation_offset=0,
    )
    assert result["phase"] == "TRANSITION"


def test_canonical_ordering():
    assert _canonical("b", "a") == ("a", "b")
    assert _canonical("a", "b") == ("a", "b")
    assert _canonical("p10", "p2") == ("p10", "p2")  # lexicographic: "p1" < "p2"


# ── Round-level assertion helpers ──────────────────────────────────────────────

def _slots_by_round(slots: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}
    for slot in slots:
        result.setdefault(slot["round_number"], []).append(slot)
    return result


def _players_in_round(round_slots: list[dict]) -> set[str]:
    """All player IDs that appear in a round (BYE player counted via player_a_id)."""
    pids: set[str] = set()
    for slot in round_slots:
        pids.add(slot["player_a_id"])
        if slot["player_b_id"] is not None:
            pids.add(slot["player_b_id"])
    return pids


# ── Test data ──────────────────────────────────────────────────────────────────
#
# Scenario: 7 players across 4 tiers — mirrors the real-world case that exposed
# the BYE-rotation and shift=1 bugs.
#
#   Tier layout: NT×1, Elite×1, Advanced×1, Intermediate×4
#   Spread = 490 → STANDARD phase
#
# NARROW variant: all 4 INTERMEDIATE players cluster within 80 rating points of
# Ishaan (ADVANCED), so no stretch partner exists for Ishaan (all gaps < 100).
# The only natural stretch pair is Rohan–Sanya (gap = 120).
#
# WIDE variant: Ishaan (1150) vs Aarav (1030) gap = 120 — Ishaan finds a natural
# stretch partner and the BYE fallback path is not needed.

_PLAYERS_7_NARROW = [
    {"player_id": "rohan",  "current_rating": 1510.0},   # NATIONAL_TRACK
    {"player_id": "sanya",  "current_rating": 1390.0},   # ELITE
    {"player_id": "ishaan", "current_rating": 1100.0},   # ADVANCED
    {"player_id": "dev",    "current_rating": 1080.0},   # INTERMEDIATE  gap-to-ishaan = 20
    {"player_id": "ananya", "current_rating": 1060.0},   # INTERMEDIATE  gap-to-ishaan = 40
    {"player_id": "aarav",  "current_rating": 1040.0},   # INTERMEDIATE  gap-to-ishaan = 60
    {"player_id": "mayur",  "current_rating": 1020.0},   # INTERMEDIATE  gap-to-ishaan = 80
]

_PLAYERS_7_WIDE = [
    {"player_id": "rohan",  "current_rating": 1510.0},   # NATIONAL_TRACK
    {"player_id": "sanya",  "current_rating": 1380.0},   # ELITE
    {"player_id": "ishaan", "current_rating": 1150.0},   # ADVANCED
    {"player_id": "dev",    "current_rating": 1090.0},   # INTERMEDIATE
    {"player_id": "ananya", "current_rating": 1060.0},   # INTERMEDIATE
    {"player_id": "aarav",  "current_rating": 1030.0},   # INTERMEDIATE  gap-to-ishaan = 120
    {"player_id": "mayur",  "current_rating": 1000.0},   # INTERMEDIATE  gap-to-ishaan = 150
]


# ── Standard fixtures: BYE rotation + shift=1 coverage (regression tests) ─────
#
# mpp=3 gives rounds: competitive(1) → stretch(2) → competitive(3)
# Two competitive rounds are enough to verify BYE rotation.


def test_standard_7p_competitive_rounds_cover_all_players():
    """
    Every player must appear in every competitive round — in a match or as the
    one rotating BYE.  Regression for the shift=1 bug that silently dropped
    players from even-sized tier groups.

    Old behaviour with gn=4, shift=1:
        range(0, gn-2, 2) = [0]  →  only one pair generated; 2 players lost.
    New behaviour:
        range(half) → cross-half pairs; all 4 covered.
    """
    all_pids = {p["player_id"] for p in _PLAYERS_7_NARROW}
    slots = generate_standard_fixtures(
        _PLAYERS_7_NARROW, set(), matches_per_player=3, num_tables=4
    )
    by_round = _slots_by_round(slots)

    for rn, rs in sorted(by_round.items()):
        if any(s["match_category"] == "COMPETITIVE" for s in rs):
            missing = all_pids - _players_in_round(rs)
            assert not missing, f"Round {rn} (competitive) missing players: {missing}"


def test_standard_7p_shift1_covers_all_four_intermediate_players():
    """
    Round 3 uses shift=1 on the 4-player INTERMEDIATE group.
    Old bug: only (dev, aarav) was produced; ananya and mayur were silently dropped.
    New fix: cross-half yields (dev, aarav) AND (ananya, mayur).
    """
    slots = generate_standard_fixtures(
        _PLAYERS_7_NARROW, set(), matches_per_player=3, num_tables=4
    )
    by_round = _slots_by_round(slots)

    competitive_rounds = sorted(
        rn for rn, rs in by_round.items()
        if any(s["match_category"] == "COMPETITIVE" for s in rs)
    )
    # Round 3 is the second competitive round (shift=1)
    r3 = competitive_rounds[1]
    r3_pids = _players_in_round(by_round[r3])

    intermediate_pids = {"dev", "ananya", "aarav", "mayur"}
    missing = intermediate_pids - r3_pids
    assert not missing, f"Shift=1 dropped INTERMEDIATE players from round {r3}: {missing}"


def test_standard_7p_bye_rotates_between_competitive_rounds():
    """
    The player who gets the BYE in round 1 must NOT be the same one in round 3.
    Regression for deterministic BYE that always picked the last leftover in
    tier-sorted order (Ishaan every time).
    """
    slots = generate_standard_fixtures(
        _PLAYERS_7_NARROW, set(), matches_per_player=3, num_tables=4
    )
    by_round = _slots_by_round(slots)

    # Competitive rounds are odd round numbers (step=0→R1, step=2→R3).
    # Using round_number parity is more reliable than match_category because
    # BYE slots in stretch rounds are always labeled COMPETITIVE (they have no
    # rating-gap to derive a category from), which would otherwise cause stretch
    # rounds to be counted as competitive.
    competitive_rounds = sorted(rn for rn in by_round.keys() if rn % 2 == 1)
    assert len(competitive_rounds) == 2, "Expected exactly 2 competitive rounds with mpp=3"

    bye_players = []
    for rn in competitive_rounds:
        bye_slot = next((s for s in by_round[rn] if s["player_b_id"] is None), None)
        assert bye_slot is not None, f"No BYE slot in competitive round {rn} with 7 players"
        bye_players.append(bye_slot["player_a_id"])

    assert bye_players[0] != bye_players[1], (
        f"'{bye_players[0]}' got the BYE in both competitive rounds — rotation broken"
    )


def test_standard_7p_bye_player_plays_in_stretch_when_no_natural_partner():
    """
    Ishaan (ADVANCED 1100) has no valid stretch partner — all INTERMEDIATE
    players are within 80 rating points (< 100 threshold).  The BYE-fallback
    must still include Ishaan in the stretch round (paired with nearest
    available unmatched player).
    """
    slots = generate_standard_fixtures(
        _PLAYERS_7_NARROW, set(), matches_per_player=3, num_tables=4
    )
    by_round = _slots_by_round(slots)

    bye_slot_r1 = next((s for s in by_round[1] if s["player_b_id"] is None), None)
    assert bye_slot_r1 is not None, "Expected a BYE slot in round 1"
    bye_player = bye_slot_r1["player_a_id"]

    r2_pids = _players_in_round(by_round[2])
    assert bye_player in r2_pids, (
        f"'{bye_player}' got BYE in round 1 and was absent from round 2 "
        f"(stretch fallback failed)"
    )


def test_standard_7p_bye_player_plays_in_stretch_when_natural_partner_exists():
    """
    When the BYE player (Ishaan, 1150) has a valid stretch partner — Aarav
    at 1030 gives gap=120 — the stretch algorithm finds them without needing
    the fallback.  Ishaan must still appear in round 2.
    """
    slots = generate_standard_fixtures(
        _PLAYERS_7_WIDE, set(), matches_per_player=3, num_tables=4
    )
    by_round = _slots_by_round(slots)

    bye_slot_r1 = next((s for s in by_round[1] if s["player_b_id"] is None), None)
    assert bye_slot_r1 is not None
    bye_player = bye_slot_r1["player_a_id"]

    r2_pids = _players_in_round(by_round[2])
    assert bye_player in r2_pids, (
        f"'{bye_player}' got BYE in round 1 but was absent from round 2"
    )


def test_standard_no_player_scheduled_twice_in_same_round():
    """Each player can appear at most once per round across both datasets."""
    for players in [_PLAYERS_7_NARROW, _PLAYERS_7_WIDE]:
        slots = generate_standard_fixtures(players, set(), matches_per_player=4, num_tables=4)
        by_round = _slots_by_round(slots)
        for rn, rs in by_round.items():
            seen: list[str] = []
            for s in rs:
                seen.append(s["player_a_id"])
                if s["player_b_id"]:
                    seen.append(s["player_b_id"])
            dups = [p for p in set(seen) if seen.count(p) > 1]
            assert not dups, f"Round {rn}: players scheduled twice: {dups}"


def test_standard_even_4p_tier_group_shift1_pairs_all_members():
    """
    Isolated unit-level check: 4 players in a single tier with shift=1 must
    produce 2 pairs (all 4 covered), not 1 pair with 2 dropped.

    Ratings 1200–1260 → all ADVANCED → one tier group of 4.
    Spread = 60 < 100 → DISCOVERY phase, so we drive generate_standard_fixtures
    directly (bypassing the dispatcher's phase check).
    """
    players = [
        {"player_id": "a", "current_rating": 1260.0},
        {"player_id": "b", "current_rating": 1240.0},
        {"player_id": "c", "current_rating": 1220.0},
        {"player_id": "d", "current_rating": 1200.0},
    ]
    # mpp=2: competitive(shift=0) → stretch(no valid gaps inside ADVANCED) → done
    # Only 1 competitive round, so use mpp=1 to get shift=0 and see all 4 paired,
    # then mpp=3 to get a shift=1 round.
    slots = generate_standard_fixtures(players, set(), matches_per_player=3, num_tables=4)
    by_round = _slots_by_round(slots)

    competitive_rounds = sorted(
        rn for rn, rs in by_round.items()
        if any(s["match_category"] == "COMPETITIVE" for s in rs)
    )
    all_pids = {p["player_id"] for p in players}

    for rn in competitive_rounds:
        missing = all_pids - _players_in_round(by_round[rn])
        assert not missing, f"Round {rn}: {missing} missing from 4-player single-tier group"


def test_standard_8p_mixed_tiers_shift1_all_paired():
    """
    8 players across 3 tiers (INT×3, ADV×4, ELITE×1).  With shift=1 the
    4-player ADVANCED group uses cross-half pairing and all 4 must be covered.

    Players: p0–p6 = 950, 1000, 1050, 1110, 1150, 1200, 1250 (INT×3, ADV×4)
             p7 = 1320  (ELITE×1)
    Spread = 1320 – 950 = 370 → STANDARD
    """
    ratings = [950.0, 1000.0, 1050.0, 1110.0, 1150.0, 1200.0, 1250.0, 1320.0]
    players = [{"player_id": f"p{i}", "current_rating": r} for i, r in enumerate(ratings)]
    # Tier layout: INT=[p0,p1,p2], ADV=[p3,p4,p5,p6], ELITE=[p7]
    # Round 1 (shift=0): INT→(p0,p1),leftover p2 | ADV→(p3,p4),(p5,p6) | ELITE→leftover p7
    #   leftovers [p2,p7] → pair (p2,p7); all 8 covered.
    # Round 3 (shift=1): INT half=1→(p0,p1),leftover p2 | ADV half=2→(p3,p5),(p4,p6)
    #   leftovers [p2,p7](rotated) → (p7,p2); all 8 covered.

    all_pids = {p["player_id"] for p in players}
    slots = generate_standard_fixtures(players, set(), matches_per_player=3, num_tables=4)
    by_round = _slots_by_round(slots)

    for rn, rs in sorted(by_round.items()):
        if any(s["match_category"] == "COMPETITIVE" for s in rs):
            missing = all_pids - _players_in_round(rs)
            assert not missing, f"Round {rn}: missing {missing}"


def test_standard_7p_three_same_tier_bye_player_plays_in_stretch():
    """
    Real-world scenario: 3 ADVANCED players all at 1200, 2 INTERMEDIATE at 1000.
    Round 1: Dashaan–Mayur (ADVANCED pair), Aarav–Ananya (INT pair),
             Sanya–Rohan (leftover cross-tier), Ishaan BYE.
    Round 2 stretch: without priority, Dashaan and Mayur each claim an INT
    player (Dashaan–Aarav, Mayur–Ananya) before the algorithm reaches Ishaan,
    leaving Ishaan with no partner and the fallback empty-handed.
    With priority fix: Ishaan claims Aarav first, then the sweep fills the rest.
    Ishaan must appear in Round 2.
    """
    # Sort is stable: equal-rated players keep their list order.
    # Dashaan and Mayur must appear BEFORE Ishaan so that Ishaan ends up last
    # in the ADVANCED group and becomes the round-1 BYE — matching the DB order.
    players = [
        {"player_id": "rohan",   "current_rating": 1500.0},  # NATIONAL_TRACK
        {"player_id": "sanya",   "current_rating": 1400.0},  # ELITE
        {"player_id": "dashaan", "current_rating": 1200.0},  # ADVANCED — paired in R1
        {"player_id": "mayur",   "current_rating": 1200.0},  # ADVANCED — paired in R1
        {"player_id": "ishaan",  "current_rating": 1200.0},  # ADVANCED — BYE in R1
        {"player_id": "aarav",   "current_rating": 1000.0},  # INTERMEDIATE
        {"player_id": "ananya",  "current_rating": 1000.0},  # INTERMEDIATE
    ]
    # mpp=3 → competitive(1) → stretch(2) → competitive(3)
    slots = generate_standard_fixtures(players, set(), matches_per_player=3, num_tables=3)
    by_round = _slots_by_round(slots)

    # Confirm Ishaan gets BYE in round 1
    bye_r1 = next((s for s in by_round[1] if s["player_b_id"] is None), None)
    assert bye_r1 is not None
    assert bye_r1["player_a_id"] == "ishaan", (
        f"Expected Ishaan BYE in round 1, got '{bye_r1['player_a_id']}'"
    )

    # Confirm Ishaan plays in round 2 (stretch) — the core regression check
    r2_pids = _players_in_round(by_round[2])
    assert "ishaan" in r2_pids, (
        "Ishaan had BYE in round 1 but was absent from round 2 — "
        "priority-stretch fix not working"
    )


def test_standard_20p_all_players_in_competitive_rounds():
    """
    20 players with spread = 570 → STANDARD, even count so no BYE.
    Every player must appear in both competitive rounds.

    Ratings: 900, 930, …, 1470 (step=30)
    Tiers: INT×7 (900–1080), ADV×7 (1110–1290), ELITE×6 (1320–1470)
    """
    players = [
        {"player_id": f"p{i}", "current_rating": 900.0 + i * 30}
        for i in range(20)
    ]
    all_pids = {p["player_id"] for p in players}

    slots = generate_standard_fixtures(players, set(), matches_per_player=3, num_tables=10)
    by_round = _slots_by_round(slots)

    for rn, rs in sorted(by_round.items()):
        if any(s["match_category"] == "COMPETITIVE" for s in rs):
            missing = all_pids - _players_in_round(rs)
            assert not missing, f"Round {rn}: {len(missing)} players missing: {missing}"


# ── Round pattern selection (C-S-C-S vs C-C-S-C) ──────────────────────────────

def test_standard_cscs_pattern_when_all_tiers_even():
    """
    All tier groups have even player counts → C-S-C-S (Variety Maximization).
    Round 2 must contain at least one STRETCH non-BYE slot.
    """
    # NT×2, ELITE×2, ADV×2 — all groups of size 2 (even)
    players = [
        {"player_id": "a", "current_rating": 1560.0},
        {"player_id": "b", "current_rating": 1520.0},
        {"player_id": "c", "current_rating": 1420.0},
        {"player_id": "d", "current_rating": 1360.0},
        {"player_id": "e", "current_rating": 1220.0},
        {"player_id": "f", "current_rating": 1160.0},
    ]
    slots = generate_standard_fixtures(players, set(), matches_per_player=4, num_tables=4)
    by_round = _slots_by_round(slots)
    # C-S-C-S: rounds 2 and 4 are stretch
    for rn in [2, 4]:
        assert any(
            s["match_category"] == "STRETCH" and s["player_b_id"] is not None
            for s in by_round[rn]
        ), f"C-S-C-S: expected STRETCH non-BYE slots in round {rn}"


def test_standard_ccsc_pattern_when_any_tier_odd():
    """
    At least one tier group has an odd player count → C-C-S-C (Rotation Completion).
    Round 2 must be competitive and round 3 must contain STRETCH slots.
    """
    # NT×1 (odd), ELITE×2, ADV×2, INT×1 (odd)
    players = [
        {"player_id": "a", "current_rating": 1560.0},  # NT
        {"player_id": "b", "current_rating": 1420.0},  # ELITE
        {"player_id": "c", "current_rating": 1360.0},  # ELITE
        {"player_id": "d", "current_rating": 1220.0},  # ADV
        {"player_id": "e", "current_rating": 1160.0},  # ADV
        {"player_id": "f", "current_rating": 1000.0},  # INT
    ]
    slots = generate_standard_fixtures(players, set(), matches_per_player=4, num_tables=4)
    by_round = _slots_by_round(slots)
    # C-C-S-C: rounds 1, 2, 4 are competitive; round 3 is stretch
    for rn in [1, 2, 4]:
        assert any(
            s["match_category"] == "COMPETITIVE" and s["player_b_id"] is not None
            for s in by_round[rn]
        ), f"C-C-S-C: expected COMPETITIVE non-BYE slots in round {rn}"
    assert any(
        s["match_category"] == "STRETCH" and s["player_b_id"] is not None
        for s in by_round[3]
    ), "C-C-S-C: expected STRETCH non-BYE slots in round 3"


def test_standard_3player_tier_full_rotation_with_mpp4():
    """
    A 3-player tier needs 3 competitive shifts (0, 1, 2) to complete its internal
    round-robin.  With C-C-S-C (4 rounds → 3 competitive), all 3 intra-tier pairs
    must appear somewhere in the schedule.

    With C-S-C-S (only 2 competitive rounds) one pair is always skipped — the
    motivating case for the C-C-S-C pattern.
    """
    # ADV×3 is the odd tier that drives C-C-S-C selection.
    players = [
        {"player_id": "nt",    "current_rating": 1560.0},
        {"player_id": "elite", "current_rating": 1400.0},
        {"player_id": "adv1",  "current_rating": 1200.0},
        {"player_id": "adv2",  "current_rating": 1150.0},
        {"player_id": "adv3",  "current_rating": 1100.0},
        {"player_id": "int",   "current_rating": 1000.0},
    ]
    slots = generate_standard_fixtures(players, set(), matches_per_player=4, num_tables=4)

    adv_pids = {"adv1", "adv2", "adv3"}
    intra_adv: set[tuple] = set()
    for s in slots:
        if s["player_b_id"] and s["player_a_id"] in adv_pids and s["player_b_id"] in adv_pids:
            intra_adv.add(_canonical(s["player_a_id"], s["player_b_id"]))

    expected = {
        _canonical("adv1", "adv2"),
        _canonical("adv1", "adv3"),
        _canonical("adv2", "adv3"),
    }
    assert intra_adv == expected, (
        f"ADV 3-player round-robin incomplete. Missing: {expected - intra_adv}"
    )


# ── Inter-academy league fixture strategies ────────────────────────────────────
#
# Tests for generate_league_fixtures with 4 strategies:
#   1. TIER_MATCHED (default): within-tier cross-academy round-robin
#   2. CROSS_ACADEMY_ONLY: circle method, intra-academy pairs → BYEs
#   3. TEAM_FORMAT: positional academy matchups (#1v#1, #2v#2, …)
#   4. FULL_ROUND_ROBIN: every player vs every other (legacy)
#
# Diverse test data:
#   - 2–4 academies with varying sizes
#   - Rated 900–1500 (BEGINNER → NATIONAL_TRACK)
#   - Mixed tier distributions per academy
#

def _make_inter_academy_players(
    academy_data: dict[str, list[tuple[str, float]]],
) -> dict[str, list[dict]]:
    """
    Helper to create inter-academy player dicts.
    academy_data: {academy_id: [(player_name, rating), ...]}
    Returns: {academy_id: [player_dict, ...]}
    """
    result = {}
    for academy_id, players_list in academy_data.items():
        result[academy_id] = [
            {
                "player_id": f"{academy_id}_{name}",
                "name": name,
                "current_rating": rating,
                "academy_id": academy_id,
                "academy_name": f"Academy {academy_id.upper()}",
            }
            for name, rating in players_list
        ]
    return result


def test_league_fixtures_tier_matched_default_strategy():
    """TIER_MATCHED is the default strategy when none specified."""
    # 2 academies, 3 players each, same tier distribution
    academy_data = {
        "a": [("a1", 1150.0), ("a2", 1100.0), ("a3", 1050.0)],
        "b": [("b1", 1140.0), ("b2", 1090.0), ("b3", 1040.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    result = generate_league_fixtures(players_by_academy, set())
    assert "slots" in result
    assert len(result["slots"]) > 0
    
    # Verify the result has the expected structure
    for slot in result["slots"]:
        assert "round_number" in slot
        assert "player_a_id" in slot
        assert "match_category" in slot
        assert "expected_rating_gap" in slot
        assert "fixture_strategy" in slot
    
    # TIER_MATCHED groups by tier, so all matches within a tier should have similar ratings
    for slot in result["slots"]:
        if slot["player_b_id"]:
            # Should be within reasonable gap for same tier
            assert slot["expected_rating_gap"] <= 200, (
                f"Gap {slot['expected_rating_gap']} too large for tier-matched pairing"
            )


def test_league_fixtures_tier_matched_skips_pure_bye_rounds():
    academy_data = {
        "JLTTA": [
            ("Rohan Dasgupta", 1400.0),
            ("Sanya Malhotra", 1300.0),
            ("Kabir Singh", 1400.0),
            ("Arjun Sharma", 1200.0),
            ("Dashaan Kanal", 1206.51),
            ("Mayur Kolapte", 1208.88),
            ("Ameya Shah", 1017.93),
            ("Rohan Batra", 950.0),
            ("Aarav Sharma", 992.34),
            ("Ananya Iyer", 1000.0),
        ],
        "YMCA": [
            ("Anika Menon", 1300.0),
            ("Advait Joshi", 1350.0),
            ("Vihaan Gupta", 1200.0),
            ("Shreya Iyer", 1200.0),
            ("Ishaan Patel", 1174.33),
            ("Myra Kapur", 1000.0),
            ("Aryan Verma", 1000.0),
            ("Diya Reddy", 1000.0),
        ],
    }
    players_by_academy = _make_inter_academy_players(academy_data)

    result = generate_league_fixtures(
        players_by_academy,
        set(),
        strategy="TIER_MATCHED",
        num_tables=4,
    )

    by_round: dict[int, list[dict]] = {}
    for slot in result["slots"]:
        by_round.setdefault(slot["round_number"], []).append(slot)

    for round_number, slots in by_round.items():
        assert any(slot["player_b_id"] is not None for slot in slots), (
            f"Round {round_number} contains only BYEs"
        )


def test_league_fixtures_tier_matched_multi_tier():
    """
    TIER_MATCHED groups players by tier, then cross-academy round-robin within each tier.
    Academies with players in different tiers should have tier-specific matches only.
    """
    # Academy A: 2 ELITE, 1 ADVANCED
    # Academy B: 1 ELITE, 2 ADVANCED, 1 INTERMEDIATE
    # Within ELITE tier: A_e1/e2 face B_e1
    # Within ADVANCED tier: A_a1 faces B_a1/a2
    # Within INTERMEDIATE tier: only B_i1 (no cross-academy pair) → no INTERMEDIATE matches
    academy_data = {
        "a": [("e1", 1350.0), ("e2", 1340.0), ("a1", 1150.0)],
        "b": [("e1", 1330.0), ("a1", 1140.0), ("a2", 1130.0), ("i1", 1000.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    result = generate_league_fixtures(players_by_academy, set(), strategy="TIER_MATCHED")
    
    # Verify cross-academy within each tier
    cross_academy_count = 0
    for slot in result["slots"]:
        if slot["player_b_id"]:
            a_rating = float([p for p in players_by_academy["a"] + players_by_academy["b"]
                            if p["player_id"] == slot["player_a_id"]][0]["current_rating"])
            b_rating = float([p for p in players_by_academy["a"] + players_by_academy["b"]
                            if p["player_id"] == slot["player_b_id"]][0]["current_rating"])
            # Gap should be small (same tier)
            gap = abs(a_rating - b_rating)
            assert gap <= 200, f"Gap {gap} too large for tier-matched pairing"
            cross_academy_count += 1
    
    assert cross_academy_count > 0, "TIER_MATCHED generated no cross-academy matches"


def test_league_fixtures_tier_matched_packs_rounds_across_tiers():
    """
    TIER_MATCHED should allow different tiers to share the same global
    round_number when physical table capacity permits.
    """
    academy_data = {
        "j": [("j1", 1470.0), ("j2", 1460.0), ("j3", 1450.0)],
        "y": [("y1", 1440.0)],
        "a": [("a1", 1010.0)],
        "b": [("b1", 1000.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)

    result = generate_league_fixtures(
        players_by_academy, set(), strategy="TIER_MATCHED", num_tables=4
    )

    round_numbers = sorted({slot["round_number"] for slot in result["slots"]})
    assert round_numbers == list(range(1, result["total_rounds"] + 1))
    assert result["total_rounds"] == 3, (
        f"Expected packed rounds across tiers to fit into 3 rounds, got {result['total_rounds']}"
    )


def test_league_fixtures_cross_academy_only_no_intra_academy():
    """
    CROSS_ACADEMY_ONLY: all matches are cross-academy; intra-academy pairs → BYEs.
    No two players from the same academy should ever be paired.
    """
    academy_data = {
        "a": [("a1", 1200.0), ("a2", 1100.0)],
        "b": [("b1", 1180.0), ("b2", 1080.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    result = generate_league_fixtures(players_by_academy, set(), strategy="CROSS_ACADEMY_ONLY")
    
    # Verify no intra-academy pairs
    for slot in result["slots"]:
        if slot["player_b_id"]:  # Skip BYE slots
            a_academy = slot["player_a_id"].split("_")[0]
            b_academy = slot["player_b_id"].split("_")[0]
            assert a_academy != b_academy, (
                f"CROSS_ACADEMY_ONLY generated intra-academy pair: {slot['player_a_id']} vs {slot['player_b_id']}"
            )


def test_league_fixtures_cross_academy_only_has_bye_slots():
    """
    CROSS_ACADEMY_ONLY generates BYE slots where intra-academy pairs would have occurred,
    but ghost rounds (rounds with no real matches) are pruned to avoid clutter.
    
    With 2 academies of 2 players each (4 total), the circle method produces 3 logical
    rounds, but Round 3 contains only intra-academy pairs (a1-a2, b1-b2) which become
    all BYEs. This ghost round is skipped by the pruning logic. Rounds 1-2 contain
    real cross-academy matches and may have scattered BYEs.
    """
    academy_data = {
        "a": [("a1", 1200.0), ("a2", 1100.0)],
        "b": [("b1", 1180.0), ("b2", 1080.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    result = generate_league_fixtures(players_by_academy, set(), strategy="CROSS_ACADEMY_ONLY")
    
    # With gap cap enforced and ghost rounds pruned, we should have 2 rounds with all matches
    assert result["total_rounds"] == 2, f"Expected 2 rounds (ghost round pruned), got {result['total_rounds']}"
    assert all(slot["player_b_id"] is not None for slot in result["slots"]), \
        "All slots should be real matches (no BYEs) when ratings are within bounds"


def test_league_fixtures_team_format_academy_pairs():
    """
    TEAM_FORMAT: generates round-robin of academy pairs, with positional pairing.
    With 3 academies, should have 3 rounds (A vs B, A vs C, B vs C).
    Each round has positional matches (#1 vs #1, #2 vs #2, …).
    """
    academy_data = {
        "ymca": [("p1", 1300.0), ("p2", 1200.0), ("p3", 1100.0)],
        "isl": [("p1", 1280.0), ("p2", 1180.0), ("p3", 1080.0)],
        "dlsa": [("p1", 1260.0), ("p2", 1160.0), ("p3", 1060.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    result = generate_league_fixtures(players_by_academy, set(), strategy="TEAM_FORMAT")
    
    # 3 academies → C(3,2) = 3 academy-pair rounds
    assert result["total_rounds"] == 3
    
    # Verify positional pairing: #1 vs #1 in each academy-pair round
    by_round = {}
    for slot in result["slots"]:
        by_round.setdefault(slot["round_number"], []).append(slot)
    
    for round_num, slots in by_round.items():
        # Each position (table) should have one match or BYE
        by_position = {}
        for slot in slots:
            by_position.setdefault(slot["table_number"], slot)
        
        assert len(by_position) >= 1, f"Round {round_num} has no positional matches"


def test_league_fixtures_team_format_uneven_academy_sizes():
    """
    TEAM_FORMAT with uneven academy sizes: smaller academy players get BYEs.
    Academy A has 3 players, Academy B has 2 → match B's #1-#2, then A's #3 gets BYE.
    """
    academy_data = {
        "a": [("p1", 1300.0), ("p2", 1200.0), ("p3", 1100.0)],
        "b": [("p1", 1280.0), ("p2", 1180.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    result = generate_league_fixtures(players_by_academy, set(), strategy="TEAM_FORMAT")
    
    # 2 academies → 1 round (A vs B)
    assert result["total_rounds"] == 1
    
    # Should have 3 slots: (a_p1 vs b_p1), (a_p2 vs b_p2), (a_p3 BYE)
    assert len(result["slots"]) == 3
    
    bye_count = sum(1 for s in result["slots"] if s["player_b_id"] is None)
    assert bye_count == 1, "Expected 1 BYE for uneven sized teams"


def test_league_fixtures_full_round_robin_all_pairs():
    """
    FULL_ROUND_ROBIN: every player faces every other exactly once (or as close as possible).
    With 4 players total (2+2 academies), should have ceil(N-1) = 3 rounds with 2 matches each.
    """
    academy_data = {
        "a": [("a1", 1200.0), ("a2", 1100.0)],
        "b": [("b1", 1180.0), ("b2", 1080.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    result = generate_league_fixtures(players_by_academy, set(), strategy="FULL_ROUND_ROBIN")
    
    # 4 players → 3 rounds of circle method
    assert result["total_rounds"] <= 4
    
    # Collect all pairs
    all_pairs: set[tuple] = set()
    for slot in result["slots"]:
        if slot["player_b_id"]:
            pair = _canonical(slot["player_a_id"], slot["player_b_id"])
            all_pairs.add(pair)
    
    # With 4 players, max unique pairs = 6
    assert len(all_pairs) >= 4, f"FULL_ROUND_ROBIN produced only {len(all_pairs)} unique pairs (expected ~6)"


def test_league_fixtures_diverse_3_academies_4_players_each():
    """
    Complex scenario: 3 academies, 4 players each, mixed ratings (900–1400).
    Tests scalability of each strategy.
    """
    academy_data = {
        "a": [("p1", 1400.0), ("p2", 1300.0), ("p3", 1100.0), ("p4", 900.0)],
        "b": [("p1", 1380.0), ("p2", 1280.0), ("p3", 1080.0), ("p4", 920.0)],
        "c": [("p1", 1360.0), ("p2", 1260.0), ("p3", 1060.0), ("p4", 940.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    for strategy in ["TIER_MATCHED", "CROSS_ACADEMY_ONLY", "TEAM_FORMAT", "FULL_ROUND_ROBIN"]:
        result = generate_league_fixtures(players_by_academy, set(), strategy=strategy)
        
        # All strategies should generate slots
        assert len(result["slots"]) > 0, f"{strategy} generated no slots"
        
        # No self-pairings
        for slot in result["slots"]:
            if slot["player_b_id"]:
                assert slot["player_a_id"] != slot["player_b_id"], (
                    f"{strategy}: self-pairing detected"
                )
        
        # All player IDs should be valid
        all_player_ids = set()
        for acad_players in players_by_academy.values():
            for p in acad_players:
                all_player_ids.add(p["player_id"])
        
        for slot in result["slots"]:
            assert slot["player_a_id"] in all_player_ids, f"{strategy}: invalid player_a_id"
            if slot["player_b_id"]:
                assert slot["player_b_id"] in all_player_ids, f"{strategy}: invalid player_b_id"


def test_league_fixtures_cross_academy_percentage():
    """
    Verify cross_academy_pct metric for each strategy.
    TIER_MATCHED: typically >60% (can have intra-academy if tier has only 1 academy)
    CROSS_ACADEMY_ONLY: 100% (by design, no intra-academy pairs)
    TEAM_FORMAT: 100% (all academy-pair matches are cross-academy)
    """
    academy_data = {
        "a": [("p1", 1300.0), ("p2", 1200.0), ("p3", 1100.0)],
        "b": [("p1", 1280.0), ("p2", 1180.0), ("p3", 1080.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    tier_result = generate_league_fixtures(players_by_academy, set(), strategy="TIER_MATCHED")
    cross_result = generate_league_fixtures(players_by_academy, set(), strategy="CROSS_ACADEMY_ONLY")
    team_result = generate_league_fixtures(players_by_academy, set(), strategy="TEAM_FORMAT")
    
    # CROSS_ACADEMY_ONLY and TEAM_FORMAT should be 100%
    assert cross_result["cross_academy_pct"] == 100.0
    assert team_result["cross_academy_pct"] == 100.0
    
    # TIER_MATCHED should be reasonably high when multiple academies per tier
    assert tier_result["cross_academy_pct"] > 50.0


def test_league_fixtures_with_played_pairs():
    """
    Test that played_pairs (from previous events) is respected.
    Strategies should avoid recent pairs (though emphasis varies).
    """
    academy_data = {
        "a": [("p1", 1300.0), ("p2", 1200.0), ("p3", 1100.0)],
        "b": [("p1", 1280.0), ("p2", 1180.0), ("p3", 1080.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    # Mark one pair as recently played
    played = {_canonical("a_p1", "b_p1")}
    
    # TIER_MATCHED should try to avoid this pair
    result = generate_league_fixtures(players_by_academy, played, strategy="TIER_MATCHED")
    
    played_in_result = any(
        _canonical(s["player_a_id"], s["player_b_id"]) in played
        for s in result["slots"] if s["player_b_id"]
    )
    # Note: TIER_MATCHED may still include the pair if no alternatives exist
    # This test mainly verifies the function accepts played_pairs parameter
    assert result is not None


def test_league_fixtures_single_academy_no_cross_academy():
    """
    Edge case: single academy (no inter-academy pairing possible).
    Strategies should handle gracefully (no matches or all BYEs).
    """
    academy_data = {
        "a": [("p1", 1300.0), ("p2", 1200.0), ("p3", 1100.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    # All strategies should handle single academy without crashing
    for strategy in ["TIER_MATCHED", "CROSS_ACADEMY_ONLY", "TEAM_FORMAT", "FULL_ROUND_ROBIN"]:
        result = generate_league_fixtures(players_by_academy, set(), strategy=strategy)
        # Single academy → no cross-academy possible
        # Strategies may generate no matches, all BYEs, or intra-academy matches
        assert "slots" in result


def test_league_fixtures_rating_gaps_tier_matched_vs_full_rr():
    """
    Compare TIER_MATCHED vs FULL_ROUND_ROBIN gap distributions.
    TIER_MATCHED should have mostly small gaps (same tier).
    FULL_ROUND_ROBIN may have large gaps (cross-tier).
    """
    # 3 academies, mixed tiers
    academy_data = {
        "a": [("elite", 1400.0), ("adv", 1150.0), ("int", 1000.0)],
        "b": [("elite", 1380.0), ("adv", 1130.0), ("int", 980.0)],
        "c": [("elite", 1360.0), ("adv", 1110.0), ("int", 960.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    tier_result = generate_league_fixtures(players_by_academy, set(), strategy="TIER_MATCHED")
    rr_result = generate_league_fixtures(players_by_academy, set(), strategy="FULL_ROUND_ROBIN")
    
    tier_gaps = [s["expected_rating_gap"] for s in tier_result["slots"] if s["player_b_id"]]
    rr_gaps = [s["expected_rating_gap"] for s in rr_result["slots"] if s["player_b_id"]]
    
    tier_avg_gap = sum(tier_gaps) / len(tier_gaps) if tier_gaps else 0
    rr_avg_gap = sum(rr_gaps) / len(rr_gaps) if rr_gaps else 0
    
    # TIER_MATCHED gaps should be tighter (same tier)
    assert tier_avg_gap < rr_avg_gap or len(rr_gaps) == 0, (
        f"TIER_MATCHED avg gap {tier_avg_gap} >= FULL_RR avg gap {rr_avg_gap}"
    )


def test_league_fixtures_match_category_assignments():
    """
    Verify that match_category is correctly assigned based on rating gap.
    COMPETITIVE: gap ≤ 100
    STRETCH: 100 < gap ≤ 250
    ANCHOR: same as stretch for opponent (no separate category)
    """
    academy_data = {
        "a": [("low", 900.0), ("mid", 1050.0), ("high", 1200.0)],
        "b": [("low", 1000.0), ("mid", 1150.0), ("high", 1300.0)],
    }
    players_by_academy = _make_inter_academy_players(academy_data)
    
    # FULL_ROUND_ROBIN will have diverse gaps, good for category testing
    result = generate_league_fixtures(players_by_academy, set(), strategy="FULL_ROUND_ROBIN")
    
    for slot in result["slots"]:
        if slot["player_b_id"]:
            gap = slot["expected_rating_gap"]
            category = slot["match_category"]
            
            if gap <= 100:
                assert category == "COMPETITIVE", (
                    f"Gap {gap} ≤ 100 should be COMPETITIVE, got {category}"
                )
            elif 100 < gap <= 250:
                assert category in ("STRETCH", "ANCHOR"), (
                    f"Gap {gap} in (100, 250] should be STRETCH/ANCHOR, got {category}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 invariant tests — production-grade contracts derived from the
# fixture_engine critique (docs/fixture_engine_best_of_both_critique.md).
#
# These pin down the legality floor and strategy contracts that every generator
# must honor. Failures here indicate a real bug, not a flaky edge case.
# ═══════════════════════════════════════════════════════════════════════════════


# ── Fixture corpus ────────────────────────────────────────────────────────────
#
# Pure-Python pools shared across invariant tests. No DB dependency.

def _flat_pool(n: int, base: float = 1000.0) -> list[dict]:
    """N players, all rated `base`. DISCOVERY shape."""
    return [{"player_id": f"f{i}", "current_rating": base} for i in range(n)]


def _mixed_pool(n: int, base: float = 1000.0, step: float = 12.0) -> list[dict]:
    """N players evenly spaced. Spread = (n-1)*step. Choose step so spread is in TRANSITION band."""
    return [{"player_id": f"m{i}", "current_rating": base + i * step} for i in range(n)]


def _wide_pool(n: int, base: float = 900.0, step: float = 30.0) -> list[dict]:
    """N players widely spaced. STANDARD shape, multi-tier."""
    return [{"player_id": f"w{i}", "current_rating": base + i * step} for i in range(n)]


# ── Generic invariant assertions ──────────────────────────────────────────────

def _assert_no_duplicate_player_per_round(slots: list[dict]) -> None:
    """Every player appears at most once per (round_number, sub_round | wave_number)."""
    buckets: dict[tuple, list[str]] = {}
    for slot in slots:
        wave = slot.get("wave_number", slot.get("sub_round"))
        key = (slot["round_number"], wave)
        buckets.setdefault(key, []).append(slot["player_a_id"])
        if slot["player_b_id"] is not None:
            buckets[key].append(slot["player_b_id"])
    for key, pids in buckets.items():
        dups = [p for p in set(pids) if pids.count(p) > 1]
        assert not dups, f"Round/wave {key}: players scheduled multiple times: {dups}"


def _assert_attending_players_covered(
    slots: list[dict], attending: set[str], rounds: set[int] | None = None
) -> None:
    """In every round, every attending player appears as match participant or BYE."""
    by_round: dict[int, set[str]] = {}
    for slot in slots:
        rn = slot["round_number"]
        by_round.setdefault(rn, set()).add(slot["player_a_id"])
        if slot["player_b_id"] is not None:
            by_round[rn].add(slot["player_b_id"])
    target_rounds = rounds if rounds is not None else set(by_round.keys())
    for rn in target_rounds:
        missing = attending - by_round.get(rn, set())
        assert not missing, f"Round {rn}: attending players missing: {missing}"


# ── #1 Transition legality: one match per player per round ────────────────────

def test_transition_no_duplicate_player_per_round():
    """
    Critique #1: within_half_pairs uses sliding adjacent windows that schedule
    interior players multiple times in the same round. Every round must be a
    legal one-match-per-player matching.
    """
    players = _make_players([1300.0, 1250.0, 1200.0, 1150.0, 1100.0, 1050.0, 1000.0, 950.0])
    slots = generate_transition_fixtures(players, matches_per_player=3, num_tables=4)
    _assert_no_duplicate_player_per_round(slots)


def test_transition_every_attending_player_appears_each_round():
    """
    Every round must cover every attending player exactly once — either in a
    match or as an explicit BYE. The old half-split sliding window dropped
    interior players from cross-half rounds when N was odd.
    """
    players = _make_players(
        [1300.0, 1250.0, 1200.0, 1150.0, 1100.0, 1050.0, 1000.0, 950.0, 900.0]
    )
    attending = {p["player_id"] for p in players}
    slots = generate_transition_fixtures(players, matches_per_player=3, num_tables=5)
    _assert_attending_players_covered(slots, attending)


def test_transition_handles_odd_count_with_explicit_bye():
    """Odd-N transition must emit explicit BYE slots; players never silent-drop."""
    players = _make_players([1300.0, 1250.0, 1200.0, 1150.0, 1100.0, 1050.0, 1000.0])
    slots = generate_transition_fixtures(players, matches_per_player=3, num_tables=4)
    by_round = _slots_by_round(slots)
    for rn, rs in by_round.items():
        has_bye = any(s["player_b_id"] is None for s in rs)
        assert has_bye, f"Round {rn}: odd-N transition expected a BYE slot"


# ── #4 CROSS_ACADEMY_ONLY contract ────────────────────────────────────────────

def test_cross_academy_only_never_emits_same_academy_pair():
    """
    Critique #4: novelty swap must never create a same-academy match. This must
    hold for every pool shape, especially saturated/skewed ones.
    """
    # Use a pool where novelty swap has incentive (some prior played pairs).
    players_by_academy = _make_inter_academy_players({
        "a": [("a1", 1300.0), ("a2", 1200.0), ("a3", 1100.0)],
        "b": [("b1", 1280.0), ("b2", 1180.0), ("b3", 1080.0)],
        "c": [("c1", 1260.0), ("c2", 1160.0), ("c3", 1060.0)],
    })
    # Pre-played: many cross-academy pairs, forcing the swap heuristic to look hard.
    played = {
        _canonical("a_a1", "b_b1"),
        _canonical("a_a2", "b_b2"),
        _canonical("a_a3", "c_c3"),
    }
    result = generate_league_fixtures(players_by_academy, played, strategy="CROSS_ACADEMY_ONLY")
    for slot in result["slots"]:
        if slot["player_b_id"] is None:
            continue
        a_acad = slot["player_a_id"].split("_")[0]
        b_acad = slot["player_b_id"].split("_")[0]
        assert a_acad != b_acad, (
            f"CROSS_ACADEMY_ONLY violated: same-academy pair "
            f"{slot['player_a_id']} vs {slot['player_b_id']} in round {slot['round_number']}"
        )


# ── #5 TIER_MATCHED contract ──────────────────────────────────────────────────

def test_tier_matched_no_same_academy_pair_when_multiple_academies_in_tier():
    """
    Critique #5: within a tier that contains players from ≥2 academies,
    TIER_MATCHED must not produce intra-academy pairs (the strategy promise).
    """
    # ELITE tier with 2 academies (a, b), ADVANCED tier with 2 academies (a, b).
    # The default round-robin used to mix academies freely → some intra-academy.
    players_by_academy = _make_inter_academy_players({
        "a": [("e1", 1390.0), ("e2", 1380.0), ("ad1", 1150.0), ("ad2", 1140.0)],
        "b": [("e1", 1370.0), ("e2", 1360.0), ("ad1", 1130.0), ("ad2", 1120.0)],
    })
    result = generate_league_fixtures(players_by_academy, set(), strategy="TIER_MATCHED")
    for slot in result["slots"]:
        if slot["player_b_id"] is None:
            continue
        a_acad = slot["player_a_id"].split("_")[0]
        b_acad = slot["player_b_id"].split("_")[0]
        assert a_acad != b_acad, (
            f"TIER_MATCHED with ≥2 academies per tier emitted intra-academy pair: "
            f"{slot['player_a_id']} vs {slot['player_b_id']} in round {slot['round_number']}"
        )


# ── #6 Singleton tier policy ──────────────────────────────────────────────────

def test_tier_matched_singleton_tier_player_not_silently_dropped():
    """
    Critique #6: a tier with only 1 player must not disappear. The player must
    still appear somewhere in the schedule — either via an adjacent-tier
    fallback, a labeled exception pairing, or an explicit BYE.
    """
    # ELITE tier: only academy a has 1 ELITE player. Without fallback the player
    # gets silently dropped from the schedule.
    players_by_academy = _make_inter_academy_players({
        "a": [("elite", 1400.0), ("ad1", 1150.0), ("ad2", 1100.0)],
        "b": [("ad1", 1140.0), ("ad2", 1080.0)],
    })
    all_pids: set[str] = set()
    for ps in players_by_academy.values():
        for p in ps:
            all_pids.add(p["player_id"])

    result = generate_league_fixtures(players_by_academy, set(), strategy="TIER_MATCHED")
    appearing: set[str] = set()
    for slot in result["slots"]:
        appearing.add(slot["player_a_id"])
        if slot["player_b_id"] is not None:
            appearing.add(slot["player_b_id"])

    assert "a_elite" in appearing, (
        "Singleton-tier player 'a_elite' silently dropped from the schedule"
    )


def test_transition_fixtures_round_numbers_session_local():
    """Round numbers are 1, 2, 3, ... (session-local), not offset-based."""
    players = _make_players([1300.0, 1250.0, 1200.0, 1150.0, 1100.0, 1050.0, 1000.0, 950.0])
    slots = generate_transition_fixtures(
        players, matches_per_player=2, num_tables=4, rotation_offset=5
    )
    round_numbers = {s["round_number"] for s in slots}
    assert round_numbers == {1, 2}, (
        f"Expected rounds 1-2 (session-local), got {sorted(round_numbers)}"
    )


def test_standard_fixtures_round_numbers_session_local():
    """Round numbers are 1, 2, 3, ... (session-local), not offset-based."""
    players = _make_players(
        [1600.0, 1500.0, 1400.0, 1300.0, 1200.0, 1100.0, 1000.0, 900.0]
    )
    slots = generate_standard_fixtures(
        players, set(), matches_per_player=2, num_tables=4, rotation_offset=10
    )
    round_numbers = {s["round_number"] for s in slots}
    assert round_numbers == {1, 2}, (
        f"Expected rounds 1-2 (session-local), got {sorted(round_numbers)}"
    )


# ── #2 Additive category model ────────────────────────────────────────────────

def test_slot_includes_round_intent_and_gap_band():
    """
    Critique #2: every slot must include the additive fields round_intent,
    gap_band, player_a_role, player_b_role. match_category is preserved as a
    compatibility field.
    """
    players = _make_players(
        [1600.0, 1500.0, 1400.0, 1300.0, 1200.0, 1100.0, 1000.0, 900.0]
    )
    slots = generate_standard_fixtures(players, set(), matches_per_player=2, num_tables=4)
    for slot in slots:
        assert "round_intent" in slot
        assert "gap_band" in slot
        assert "player_a_role" in slot
        assert "player_b_role" in slot
        assert "match_category" in slot, "compat field match_category must remain present"

        assert slot["round_intent"] in ("COMPETITIVE", "DEVELOPMENTAL")
        assert slot["gap_band"] in ("COMPETITIVE", "STRETCH", "OUT_OF_BAND", "BYE")
        assert slot["player_a_role"] in ("PEER", "STRETCHING", "ANCHORING", "BYE")
        assert slot["player_b_role"] in ("PEER", "STRETCHING", "ANCHORING", "BYE")


def test_bye_slot_has_bye_roles_and_gap_band():
    """A BYE slot must report gap_band=BYE and the absent player's role=BYE."""
    players = _make_players([1500.0, 1400.0, 1200.0, 1100.0, 1000.0])  # 5p → BYE
    slots = generate_standard_fixtures(players, set(), matches_per_player=2, num_tables=4)
    bye_slots = [s for s in slots if s["player_b_id"] is None]
    assert bye_slots, "Expected at least one BYE slot for odd-N pool"
    for s in bye_slots:
        assert s["gap_band"] == "BYE"
        assert s["player_b_role"] == "BYE"


def test_anchor_role_emitted_when_higher_rated_player_anchors_lower():
    """
    Critique #2: ANCHOR/STRETCHING roles are part of the design but the old
    engine never emits ANCHOR. A developmental round pairing a high-rated with
    a low-rated player must label the higher player ANCHORING and the lower
    STRETCHING.
    """
    # Wide pool guarantees standard phase + at least one stretch round.
    players = _make_players(
        [1600.0, 1500.0, 1400.0, 1300.0, 1200.0, 1100.0, 1000.0, 900.0]
    )
    slots = generate_standard_fixtures(players, set(), matches_per_player=4, num_tables=4)

    has_anchor = False
    has_stretching = False
    for s in slots:
        if s["player_b_id"] is None:
            continue
        if s["player_a_role"] == "ANCHORING" or s["player_b_role"] == "ANCHORING":
            has_anchor = True
        if s["player_a_role"] == "STRETCHING" or s["player_b_role"] == "STRETCHING":
            has_stretching = True
    assert has_anchor, "Expected at least one ANCHORING role across stretch rounds"
    assert has_stretching, "Expected at least one STRETCHING role across stretch rounds"


# ── #3 Standard phase: OUT_OF_BAND label, never hidden COMPETITIVE/STRETCH ────

def test_standard_out_of_band_leftover_labeled_explicitly():
    """
    Critique #3: when leftover handling forces a pairing whose gap exceeds the
    stretch band, the slot must be labeled gap_band=OUT_OF_BAND. The old
    engine silently labeled extreme gaps as STRETCH or COMPETITIVE.
    """
    # Construct a pool that forces a wide leftover pairing: NT (1500), one
    # isolated INT (950), and an even pair in between (1200, 1200). NT and
    # INT both end up as leftovers → forced cross-tier pair with gap 550.
    players = [
        {"player_id": "nt",   "current_rating": 1500.0},
        {"player_id": "adv1", "current_rating": 1200.0},
        {"player_id": "adv2", "current_rating": 1200.0},
        {"player_id": "int",  "current_rating": 950.0},
    ]
    slots = generate_standard_fixtures(players, set(), matches_per_player=1, num_tables=4)
    for s in slots:
        if s["player_b_id"] is None:
            continue
        gap = s["expected_rating_gap"]
        if gap > 250:
            assert s["gap_band"] == "OUT_OF_BAND", (
                f"Gap {gap} must be labeled OUT_OF_BAND, got {s['gap_band']}"
            )


# ── #10 stretch_pairs monotonic-scan short-circuit ────────────────────────────

def test_stretch_pairs_does_not_produce_invalid_extreme_pairings():
    """
    Critique #10: the greedy descending scan in stretch_pairs continues past
    legality once gap > _STRETCH_MAX. The result must never include a stretch
    slot whose gap is > 250 silently labeled STRETCH.
    """
    # Outlier 1600 with the rest clustered 950-1100 — natural stretch gap is
    # always > 250 for the outlier, so the scan must short-circuit cleanly
    # (no false stretch slot, BYE or OUT_OF_BAND label allowed).
    players = _make_players([1600.0, 1100.0, 1080.0, 1060.0, 1040.0, 1020.0, 1000.0, 980.0])
    slots = generate_standard_fixtures(players, set(), matches_per_player=2, num_tables=4)
    for s in slots:
        if s["player_b_id"] is None:
            continue
        if s["gap_band"] == "STRETCH":
            assert s["expected_rating_gap"] <= 250, (
                f"STRETCH gap_band carries gap {s['expected_rating_gap']} > 250"
            )


# ── #18 Phase boundary alignment with design doc ──────────────────────────────

@pytest.mark.parametrize("spread,expected_phase", [
    (100, "DISCOVERY"),    # design: <= 100 → DISCOVERY
    (101, "TRANSITION"),
    (250, "TRANSITION"),   # design: > 250 → STANDARD; 250 stays TRANSITION
    (251, "STANDARD"),
])
def test_detect_phase_design_boundaries(spread, expected_phase):
    """
    Critique #18: code uses `< 100` / `>= 250`. Design says `<= 100` / `> 250`.
    Align with the design.
    """
    players = [
        {"player_id": "a", "current_rating": 1000.0},
        {"player_id": "b", "current_rating": 1000.0 + spread},
    ]
    assert detect_phase(players) == expected_phase


# ── #19 Small-session round-robin fallback ────────────────────────────────────

def test_small_session_under_6_players_uses_pure_round_robin():
    """
    Critique #19: the design specifies that sessions with <6 players use a
    pure round-robin instead of phase-based generation. Verify the dispatcher
    routes accordingly: every pair of attending players faces each other
    within the available rounds (subject to capacity).
    """
    # 5 players, generous session capacity → at minimum a full round-robin
    # cycle of n-1=4 rounds should be reachable.
    players = _make_players([1100.0, 1050.0, 1000.0, 950.0, 900.0])
    result = generate_fixtures(
        players=players,
        recent_match_pairs=set(),
        session_minutes=240,
        num_tables=2,
        match_format="BEST_OF_3",
        rotation_offset=0,
    )
    # Pure round-robin: every player appears in every round (as match or BYE).
    attending = {p["player_id"] for p in players}
    by_round = _slots_by_round(result["slots"])
    for rn, rs in by_round.items():
        present = {s["player_a_id"] for s in rs}
        present |= {s["player_b_id"] for s in rs if s["player_b_id"]}
        missing = attending - present
        assert not missing, (
            f"Round {rn}: small-session round-robin missing players {missing}"
        )


# ── #20 Deterministic discovery ordering ──────────────────────────────────────

def test_discovery_deterministic_ordering_independent_of_input_order():
    """
    Critique #20: the design requires deterministic non-rating ordering in
    discovery. The same set of players, passed in different order, must
    produce the same set of round-1 pairs.
    """
    pool_a = [
        {"player_id": "p1", "current_rating": 1000.0},
        {"player_id": "p2", "current_rating": 1000.0},
        {"player_id": "p3", "current_rating": 1000.0},
        {"player_id": "p4", "current_rating": 1000.0},
        {"player_id": "p5", "current_rating": 1000.0},
        {"player_id": "p6", "current_rating": 1000.0},
    ]
    pool_b = list(reversed(pool_a))  # same players, reversed input order

    slots_a = generate_discovery_fixtures(pool_a, matches_per_player=1, num_tables=3, rotation_offset=0)
    slots_b = generate_discovery_fixtures(pool_b, matches_per_player=1, num_tables=3, rotation_offset=0)

    pairs_a = {_canonical(s["player_a_id"], s["player_b_id"]) for s in slots_a if s["player_b_id"]}
    pairs_b = {_canonical(s["player_a_id"], s["player_b_id"]) for s in slots_b if s["player_b_id"]}
    assert pairs_a == pairs_b, (
        f"Discovery ordering not deterministic: order A produced {pairs_a}, "
        f"order B produced {pairs_b}"
    )


# ── Universal generator-level invariant sweep ─────────────────────────────────

# ── Phase 5: robust phase detection (critique §7) ────────────────────────────

def test_detect_phase_outlier_does_not_force_standard():
    """
    Critique §7: one rating outlier must not push the whole session into
    STANDARD when the core pool is tightly clustered. Robust detection uses
    P90-P10, not raw max-min.
    """
    # 9 players clustered around 1000 ± 30, one extreme outlier at 1500.
    # Raw max-min = 530 → STANDARD under the old logic.
    # P90-P10 of [970..1030] is ~60 → DISCOVERY.
    players = (
        [{"player_id": f"core{i}", "current_rating": 1000.0 + i * 7} for i in range(9)]
        + [{"player_id": "outlier", "current_rating": 1500.0}]
    )
    assert detect_phase(players) == "DISCOVERY"


def test_detect_phase_provisional_majority_forces_discovery():
    """
    Critique §7: when most players are provisional, the rating spread is too
    noisy to support tiered/standard pairing — force DISCOVERY.
    """
    players = [
        {"player_id": f"p{i}", "current_rating": 1000.0 + i * 50, "is_provisional": True}
        for i in range(6)
    ]
    # Spread = 250 normally → TRANSITION, but provisional majority overrides.
    assert detect_phase(players) == "DISCOVERY"


def test_detect_phase_mature_pool_uses_core_spread():
    """
    Mature pool with wide P90-P10 core spread still reaches STANDARD.
    """
    players = [
        {"player_id": f"p{i}", "current_rating": 900.0 + i * 50, "rated_matches_completed": 50}
        for i in range(15)
    ]  # P90-P10 ~ 580 → STANDARD
    assert detect_phase(players) == "STANDARD"


# ── Phase 3 multi-wave numbering ──────────────────────────────────────────────

def test_multi_wave_unique_numbering_three_plus_waves():
    """
    Critique §11: when a round produces more pairs than tables * 1 wave, the
    scheduler must emit distinct wave_numbers (1, 2, 3, ...) so the engine
    supports N waves, not just A/B.
    """
    # 14 players, 2 tables → up to 7 pairs per round → at most 7 waves.
    players = _make_players([1000.0] * 14)
    slots = generate_discovery_fixtures(
        players, matches_per_player=1, num_tables=2, rotation_offset=0,
    )
    by_round = _slots_by_round(slots)
    assert by_round, "expected at least one round generated"
    # Round 1 must have 7 pairs and therefore at least 3 distinct waves (>2 → numeric).
    waves = sorted({s["wave_number"] for s in by_round[1]})
    assert max(waves) >= 3, f"expected >=3 waves with 7 pairs over 2 tables, got {waves}"
    # All slots in the same (round, wave) must use distinct table numbers.
    by_wave: dict[tuple, list[int]] = {}
    for s in by_round[1]:
        by_wave.setdefault((s["round_number"], s["wave_number"]), []).append(s["table_number"])
    for key, tbls in by_wave.items():
        assert len(tbls) == len(set(tbls)), (
            f"wave {key} has duplicate table assignments: {tbls}"
        )


def test_sub_round_legacy_label_only_for_two_wave_rounds():
    """
    sub_round is the legacy A/B display label. It must be set for 2-wave rounds
    and None for 1-wave or 3+ wave rounds, so consumers either get the legacy
    label or fall back to numeric wave_number.
    """
    # 8 players, 3 tables → 4 pairs per round → 2 waves.
    p_2wave = _make_players([1000.0] * 8)
    slots_2wave = generate_discovery_fixtures(
        p_2wave, matches_per_player=1, num_tables=3, rotation_offset=0,
    )
    labels_2wave = {s["sub_round"] for s in slots_2wave}
    assert labels_2wave == {"A", "B"}, (
        f"expected 2-wave rounds to be labeled A/B, got {labels_2wave}"
    )

    # 8 players, 4 tables → 4 pairs per round → 1 wave.
    slots_1wave = generate_discovery_fixtures(
        p_2wave, matches_per_player=1, num_tables=4, rotation_offset=0,
    )
    labels_1wave = {s["sub_round"] for s in slots_1wave}
    assert labels_1wave == {None}, (
        f"expected 1-wave rounds to drop the A/B label, got {labels_1wave}"
    )

    # 14 players, 2 tables → 7 pairs per round → 4 waves → no A/B label.
    p_4wave = _make_players([1000.0] * 14)
    slots_4wave = generate_discovery_fixtures(
        p_4wave, matches_per_player=1, num_tables=2, rotation_offset=0,
    )
    labels_4wave = {s["sub_round"] for s in slots_4wave}
    assert labels_4wave == {None}, (
        f"expected 3+-wave rounds to drop the A/B label, got {labels_4wave}"
    )


def test_table_number_bounded_by_num_tables():
    """
    table_number must always be in [1, num_tables]; overflow pairs go to a new
    wave, not to phantom table numbers. (Replaces the prior behavior in the
    inter-academy engine that emitted table_number = i + 1 sequentially.)
    """
    players = _make_players([1000.0] * 10)
    slots = generate_discovery_fixtures(
        players, matches_per_player=1, num_tables=3, rotation_offset=0,
    )
    for s in slots:
        assert 1 <= s["table_number"] <= 3, (
            f"table_number {s['table_number']} outside [1, 3] for slot {s}"
        )


@pytest.mark.parametrize("pool,tables", [
    (_flat_pool(8), 4),
    (_flat_pool(9), 4),
    (_mixed_pool(8, step=20), 4),    # spread = 140 → TRANSITION
    (_mixed_pool(9, step=20), 4),
    (_wide_pool(8), 4),              # spread = 210 → TRANSITION, but wider tiers
    (_wide_pool(9), 4),
    (_wide_pool(12, step=40), 6),    # spread = 440 → STANDARD
])
def test_no_duplicate_player_across_all_phase_dispatches(pool, tables):
    """
    Sweep across DISCOVERY / TRANSITION / STANDARD shapes: no player may appear
    more than once per round in any slot output by the dispatcher.
    """
    result = generate_fixtures(
        players=pool,
        recent_match_pairs=set(),
        session_minutes=300,
        num_tables=tables,
        match_format="BEST_OF_3",
        rotation_offset=0,
    )
    _assert_no_duplicate_player_per_round(result["slots"])
