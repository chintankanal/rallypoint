"""
pairing_solver — constrained min-cost matching for a single round of fixtures.

Per docs/fixture_engine_phased_impl_plan.md Phase 4 and critique §17, the
fixture engine moves from greedy per-tier pairing toward a small solver that:

  1. Builds candidate edges respecting hard constraints
     (gap caps, academy restrictions, forbidden rematches).
  2. Scores each edge with a soft cost (gap deviation, rematch harm,
     out-of-band penalty).
  3. Finds the maximum-cardinality, minimum-cost matching.

Implementation uses networkx.max_weight_matching, which finds the maximum
weight matching (we encode "min cost" as "max weight" with weight = BIG - cost
and BIG large enough that more edges is always preferred over fewer).

Players not picked by the matching are returned as BYE candidates; the caller
decides how to label them (the engine emits BYE slots).
"""
from typing import Callable, Optional

import networkx as nx

from app.services.rematch_policy import (
    RematchContext,
    RematchPolicy,
    DEFAULT_POLICY,
    harm_score,
    is_forbidden,
)

# Encoding for max_weight_matching: weight = _EDGE_BIAS - cost. _EDGE_BIAS must
# exceed any plausible cost so any edge beats no edge (max-cardinality semantics).
_EDGE_BIAS = 1_000_000.0


def _canonical(pid_a: str, pid_b: str) -> tuple[str, str]:
    return (pid_a, pid_b) if pid_a < pid_b else (pid_b, pid_a)


def solve_round(
    pids: list[str],
    *,
    gap_fn: Callable[[str, str], float],
    max_gap: float,
    rematch_ctx: RematchContext,
    rematch_phase: str = "STANDARD",
    policy: RematchPolicy = DEFAULT_POLICY,
    forbidden_edges: Optional[set] = None,
    extra_cost_fn: Optional[Callable[[str, str, float], float]] = None,
    competitive_max: float = 100.0,
    stretch_max: float = 250.0,
) -> tuple[list[tuple], list[str]]:
    """
    Solve a single-round matching for `pids`.

    Parameters
    ----------
    pids:
        Player IDs available for pairing this round. May be of any size; the
        solver returns a matching plus the BYE list.
    gap_fn:
        Callable returning the rating gap between two pids. The solver itself
        is rating-agnostic; gaps are only used in scoring.
    max_gap:
        Hard cap. Pairs whose gap exceeds this are not added to the graph at
        all (forced BYE for both players unless reachable via other edges).
    rematch_ctx, rematch_phase, policy:
        Threaded into the rematch harm scoring per critique §17.
    forbidden_edges:
        Optional set of canonical pairs the caller wants treated as forbidden
        (e.g. same-academy pairs in CROSS_ACADEMY_ONLY).
    extra_cost_fn:
        Optional callable (a, b, gap) -> additional cost. Lets the caller plug
        in strategy-specific scoring (e.g. tier-preference bonuses).
    competitive_max, stretch_max:
        Gap-band thresholds used to apply an out-of-band penalty so the solver
        prefers gaps in the competitive/stretch bands when alternatives exist.

    Returns
    -------
    (pairs, byes)
        pairs : list of canonical (a, b) tuples that the solver matched.
        byes  : list of player ids that the matching left unpaired.
    """
    if not pids:
        return [], []
    forbidden_edges = forbidden_edges or set()

    g = nx.Graph()
    g.add_nodes_from(pids)

    for i, a in enumerate(pids):
        for b in pids[i + 1:]:
            canon = _canonical(a, b)
            if canon in forbidden_edges:
                continue
            if is_forbidden(canon, rematch_ctx, policy=policy):
                # Hard rematch cap — leave the edge out unless we need fallback.
                continue
            gap = gap_fn(a, b)
            if gap > max_gap:
                continue

            cost = gap
            # Out-of-band penalty: prefer competitive over stretch over out-of-band
            # when alternatives exist within max_gap.
            if gap > stretch_max:
                cost += 2000.0
            elif gap > competitive_max:
                cost += 50.0
            cost += harm_score(canon, rematch_ctx, phase_or_strategy=rematch_phase, policy=policy)
            if extra_cost_fn is not None:
                cost += extra_cost_fn(a, b, gap)

            g.add_edge(a, b, weight=_EDGE_BIAS - cost)

    matching = nx.max_weight_matching(g, maxcardinality=True)
    pairs: list[tuple] = [_canonical(a, b) for a, b in matching]
    matched: set[str] = {p for pair in pairs for p in pair}
    byes: list[str] = [pid for pid in pids if pid not in matched]
    return pairs, byes


def solve_round_with_fallback(
    pids: list[str],
    *,
    gap_fn: Callable[[str, str], float],
    max_gap: float,
    rematch_ctx: RematchContext,
    rematch_phase: str = "STANDARD",
    policy: RematchPolicy = DEFAULT_POLICY,
    forbidden_edges: Optional[set] = None,
    extra_cost_fn: Optional[Callable[[str, str, float], float]] = None,
    competitive_max: float = 100.0,
    stretch_max: float = 250.0,
) -> tuple[list[tuple], list[str]]:
    """
    Two-pass solve: first call solve_round with the rematch hard cap in effect.
    If any player is left as a BYE candidate AND there exists a previously
    forbidden rematch edge that could pair two of them within `max_gap`, run a
    second pass allowing the forbidden rematches (critique §17 "least harmful
    rematch when no alternative exists"). The forbidden_edges set is still
    honored (strategy contracts like CROSS_ACADEMY_ONLY are never relaxed).
    """
    pairs, byes = solve_round(
        pids,
        gap_fn=gap_fn,
        max_gap=max_gap,
        rematch_ctx=rematch_ctx,
        rematch_phase=rematch_phase,
        policy=policy,
        forbidden_edges=forbidden_edges,
        extra_cost_fn=extra_cost_fn,
        competitive_max=competitive_max,
        stretch_max=stretch_max,
    )
    if len(byes) < 2:
        return pairs, byes

    # Second pass: relax the rematch hard cap by using a policy variant with
    # an effectively-infinite max_recent_matches_same_pair.
    relaxed_policy = RematchPolicy(
        max_recent_matches_same_pair=10**9,
        repeat_count_penalty=policy.repeat_count_penalty,
        same_session_penalty=policy.same_session_penalty,
        phase_weight_discovery=policy.phase_weight_discovery,
        phase_weight_transition=policy.phase_weight_transition,
        phase_weight_standard=policy.phase_weight_standard,
        phase_weight_tier_matched=policy.phase_weight_tier_matched,
        phase_weight_cross_academy_only=policy.phase_weight_cross_academy_only,
        phase_weight_team_format=policy.phase_weight_team_format,
        phase_weight_full_round_robin=policy.phase_weight_full_round_robin,
    )
    extra_pairs, extra_byes = solve_round(
        byes,
        gap_fn=gap_fn,
        max_gap=max_gap,
        rematch_ctx=rematch_ctx,
        rematch_phase=rematch_phase,
        policy=relaxed_policy,
        forbidden_edges=forbidden_edges,
        extra_cost_fn=extra_cost_fn,
        competitive_max=competitive_max,
        stretch_max=stretch_max,
    )
    return pairs + extra_pairs, extra_byes
