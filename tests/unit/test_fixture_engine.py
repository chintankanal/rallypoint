"""
Unit tests for fixture_engine.py — pure Python, no DB.
Tests cover:
  - Phase detection at spread boundaries
  - Session capacity formula
  - Circle-method round-robin (N=8 even, N=9 odd)
  - Discovery fixture generation
  - Standard fixtures: BYE for odd count, recent_match_pairs dedup
  - Full dispatcher for 20 players → 30 slots
"""
import math

import pytest

from app.services.fixture_engine import (
    _canonical,
    _circle_round,
    calculate_session_capacity,
    detect_phase,
    generate_discovery_fixtures,
    generate_fixtures,
    generate_standard_fixtures,
    generate_transition_fixtures,
    rating_spread,
)


def _make_players(ratings: list[float]) -> list[dict]:
    return [
        {"player_id": f"p{i}", "current_rating": r}
        for i, r in enumerate(ratings)
    ]


# ── Phase detection ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spread,expected_phase", [
    (0,   "DISCOVERY"),
    (50,  "DISCOVERY"),
    (99,  "DISCOVERY"),
    (100, "TRANSITION"),
    (249, "TRANSITION"),
    (250, "STANDARD"),
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
    slots = generate_discovery_fixtures(players, round_offset=0, matches_per_player=4, num_tables=4)
    for slot in slots:
        if slot["player_b_id"] is not None:
            assert slot["player_a_id"] != slot["player_b_id"]


def test_discovery_fixtures_round_offset_shifts_pairs():
    players = _make_players([1000.0] * 8)
    slots_0 = generate_discovery_fixtures(players, round_offset=0, matches_per_player=1, num_tables=4)
    slots_3 = generate_discovery_fixtures(players, round_offset=3, matches_per_player=1, num_tables=4)
    pairs_0 = {(_canonical(s["player_a_id"], s["player_b_id"])) for s in slots_0 if s["player_b_id"]}
    pairs_3 = {(_canonical(s["player_a_id"], s["player_b_id"])) for s in slots_3 if s["player_b_id"]}
    assert pairs_0 != pairs_3


def test_discovery_fixtures_sub_rounds_when_more_pairs_than_tables():
    # 8 players → 4 pairs per round, 3 tables → needs sub-rounds
    players = _make_players([1000.0] * 8)
    slots = generate_discovery_fixtures(players, round_offset=0, matches_per_player=1, num_tables=3)
    sub_rounds = {s["sub_round"] for s in slots}
    assert "A" in sub_rounds
    assert "B" in sub_rounds


def test_discovery_fixtures_no_sub_rounds_when_fits():
    # 8 players → 4 pairs per round, 4 tables → fits without sub-rounds
    players = _make_players([1000.0] * 8)
    slots = generate_discovery_fixtures(players, round_offset=0, matches_per_player=1, num_tables=4)
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
    """Pairs in recent_match_pairs should not appear in the dedicated stretch round."""
    # 4 players, spread=600 → STANDARD
    # fold=floor(4/4)=1: p0(1600) vs p1(1400), p2(1200) vs p3(1000)
    players = _make_players([1600.0, 1400.0, 1200.0, 1000.0])
    pids = [p["player_id"] for p in players]  # p0, p1, p2, p3

    # Canonical order for (p0, p1)
    excluded = _canonical(pids[0], pids[1])
    recent = {excluded}

    slots = generate_standard_fixtures(players, recent, matches_per_player=2, num_tables=4)
    # Bug 2 fix: cross-tier competitive pairs with gap 100–250 are now labeled STRETCH.
    # Filter by round_number == 2 (the dedicated stretch round, step=1) to avoid
    # picking up the round-1 cross-tier pairs that also carry the STRETCH label.
    stretch_slots = [s for s in slots if s["round_number"] == 2]
    stretch_pairs = {_canonical(s["player_a_id"], s["player_b_id"]) for s in stretch_slots if s["player_b_id"]}
    assert excluded not in stretch_pairs


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
        round_offset=0,
        session_minutes=150,
        num_tables=5,
        match_format="BEST_OF_3",
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
        round_offset=0,
        session_minutes=120,
        num_tables=2,
        match_format="BEST_OF_3",
    )
    assert result["phase"] == "STANDARD"
    assert result["spread"] == 300.0


def test_generate_fixtures_zero_capacity():
    """Session too short for any match → mpp=0, slots=[]."""
    players = _make_players([1000.0, 1200.0])
    result = generate_fixtures(
        players=players,
        recent_match_pairs=set(),
        round_offset=0,
        session_minutes=20,  # 20 < 25 (BEST_OF_3 + changeover)
        num_tables=1,
        match_format="BEST_OF_3",
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
        round_offset=0,
        session_minutes=120,
        num_tables=3,
        match_format="BEST_OF_3",
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
