"""
Unit tests for app/services/pairing_solver.py and rematch_policy.py.
"""
from app.services.pairing_solver import solve_round, solve_round_with_fallback
from app.services.rematch_policy import (
    RematchContext,
    RematchPolicy,
    DEFAULT_POLICY,
    harm_score,
    is_forbidden,
)


def _ctx(counts=None, session=None) -> RematchContext:
    return RematchContext(
        recent_match_counts=dict(counts or {}),
        session_pairs=frozenset(session or set()),
    )


def _gap_from_ratings(ratings: dict) -> callable:
    return lambda a, b: abs(ratings[a] - ratings[b])


# ── rematch_policy ────────────────────────────────────────────────────────────

def test_harm_score_zero_when_no_history():
    ctx = _ctx()
    assert harm_score(("a", "b"), ctx) == 0.0


def test_harm_score_grows_with_repeat_count():
    ctx = _ctx(counts={("a", "b"): 2})
    score = harm_score(("a", "b"), ctx)
    # 2 prior * repeat_count_penalty * standard_weight (1.0)
    assert score == 2 * DEFAULT_POLICY.repeat_count_penalty


def test_harm_score_session_repeat_adds_penalty():
    ctx = _ctx(session={("a", "b")})
    assert harm_score(("a", "b"), ctx) == DEFAULT_POLICY.same_session_penalty


def test_harm_score_discovery_weighted_higher_than_standard():
    ctx = _ctx(counts={("a", "b"): 1})
    discovery = harm_score(("a", "b"), ctx, phase_or_strategy="DISCOVERY")
    standard = harm_score(("a", "b"), ctx, phase_or_strategy="STANDARD")
    assert discovery > standard


def test_is_forbidden_triggers_at_or_above_cap():
    cap = DEFAULT_POLICY.max_recent_matches_same_pair
    assert not is_forbidden(("a", "b"), _ctx(counts={("a", "b"): cap - 1}))
    assert is_forbidden(("a", "b"), _ctx(counts={("a", "b"): cap}))
    assert is_forbidden(("a", "b"), _ctx(counts={("a", "b"): cap + 1}))


# ── solver: hard constraints ──────────────────────────────────────────────────

def test_solver_returns_empty_for_empty_input():
    pairs, byes = solve_round(
        [], gap_fn=lambda a, b: 0, max_gap=100,
        rematch_ctx=_ctx(),
    )
    assert pairs == []
    assert byes == []


def test_solver_pairs_two_players_under_max_gap():
    ratings = {"a": 1000.0, "b": 1050.0}
    pairs, byes = solve_round(
        ["a", "b"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(),
    )
    assert pairs == [("a", "b")]
    assert byes == []


def test_solver_byes_both_when_gap_exceeds_max():
    ratings = {"a": 1000.0, "b": 1600.0}
    pairs, byes = solve_round(
        ["a", "b"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(),
    )
    assert pairs == []
    assert sorted(byes) == ["a", "b"]


def test_solver_forbidden_edge_treated_as_missing():
    ratings = {"a": 1000.0, "b": 1010.0, "c": 1020.0}
    pairs, byes = solve_round(
        ["a", "b", "c"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(),
        forbidden_edges={("a", "b")},
    )
    assert ("a", "b") not in pairs
    # a should still get paired (with c) or BYE-ed; never with b.
    for a_, b_ in pairs:
        assert (a_, b_) != ("a", "b")


def test_solver_returns_max_cardinality_when_possible():
    """Even when edge weights favor leaving b out, the matching must pair all 4."""
    ratings = {"a": 1000.0, "b": 1010.0, "c": 1020.0, "d": 1030.0}
    pairs, byes = solve_round(
        ["a", "b", "c", "d"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(),
    )
    matched = {p for pair in pairs for p in pair}
    assert matched == {"a", "b", "c", "d"}
    assert byes == []


# ── solver: soft constraints (rematch + out-of-band) ─────────────────────────

def test_solver_prefers_non_rematch_when_alternative_exists():
    """
    Given:  a-b is recent (1 prior), a-c is fresh, b-c gap is small too.
    With 3 players, only one pair fits in a round; the solver should pair
    (a, c) over (a, b) so b's BYE is acceptable.
    """
    ratings = {"a": 1000.0, "b": 1010.0, "c": 1020.0}
    pairs, byes = solve_round(
        ["a", "b", "c"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(counts={("a", "b"): 1}),
    )
    # The matching pairs 2 of 3; verify the chosen pair is not (a, b).
    assert ("a", "b") not in pairs
    # exactly one BYE
    assert len(byes) == 1


def test_solver_falls_back_to_rematch_only_when_no_alternative():
    """
    With only two players and a rematch history, the solver must still pair
    them — but only via the fallback wrapper.
    """
    ratings = {"a": 1000.0, "b": 1010.0}
    forbidden_count = DEFAULT_POLICY.max_recent_matches_same_pair
    # Strict pass excludes the edge → both go BYE in solve_round.
    pairs, byes = solve_round(
        ["a", "b"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(counts={("a", "b"): forbidden_count}),
    )
    assert pairs == []
    assert sorted(byes) == ["a", "b"]

    # Fallback pass allows the rematch.
    pairs, byes = solve_round_with_fallback(
        ["a", "b"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(counts={("a", "b"): forbidden_count}),
    )
    assert pairs == [("a", "b")]
    assert byes == []


def test_solver_prefers_competitive_band_over_out_of_band():
    """
    a-b: competitive band (gap 50), a-c: out-of-band (gap 350).
    With 4 players a, b, c, d where (b, d) and (c, d) both fit, the optimal
    matching pairs (a, b) [competitive] and leaves c/d to handle.
    """
    ratings = {"a": 1000.0, "b": 1050.0, "c": 1350.0, "d": 1320.0}
    # max_gap=500 admits all edges; out-of-band penalty steers away from a-c.
    pairs, _ = solve_round(
        ["a", "b", "c", "d"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=500,
        rematch_ctx=_ctx(),
    )
    assert ("a", "b") in pairs
    # c and d are within stretch band of each other (gap 30) — they should pair.
    assert ("c", "d") in pairs


def test_solver_forbidden_edges_respected_in_fallback():
    """
    Strategy contracts (CROSS_ACADEMY_ONLY, TIER_MATCHED) pass forbidden_edges;
    the fallback pass must NEVER schedule those, even when relaxing rematches.
    """
    ratings = {"a": 1000.0, "b": 1010.0}
    forbidden = {("a", "b")}
    pairs, byes = solve_round_with_fallback(
        ["a", "b"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(),
        forbidden_edges=forbidden,
    )
    assert pairs == []
    assert sorted(byes) == ["a", "b"]


def test_solver_extra_cost_fn_can_force_or_discourage_pairings():
    """
    A caller-supplied extra_cost_fn can express strategy-specific preferences
    (e.g. tier-preference bonuses). Test that a huge penalty on one edge
    deflects the matching away from it.
    """
    ratings = {"a": 1000.0, "b": 1010.0, "c": 1020.0, "d": 1030.0}

    def avoid_ab(a, b, gap):
        return 100_000 if {a, b} == {"a", "b"} else 0

    pairs, byes = solve_round(
        ["a", "b", "c", "d"],
        gap_fn=_gap_from_ratings(ratings),
        max_gap=200,
        rematch_ctx=_ctx(),
        extra_cost_fn=avoid_ab,
    )
    assert ("a", "b") not in pairs
    matched = {p for pair in pairs for p in pair}
    assert matched == {"a", "b", "c", "d"}
