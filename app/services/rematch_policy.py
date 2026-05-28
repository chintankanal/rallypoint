"""
rematch_policy — harm-scoring for repeated pairings.

Per docs/fixture_engine_best_of_both_critique.md §17, fixture-generation needs
its own rematch policy at pairing time rather than relying solely on the
downstream `diminishing_signal_applied` damping in match_service. This module
provides a small, pure-Python harm score that the pairing solver consults.

The fixture engine remains DB-free; the caller passes in
`recent_match_counts[(canonical_pair)]` and `session_pairs` for the current
session, and this module reduces them to a numeric penalty per candidate pair.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RematchPolicy:
    """
    Tunable per-strategy rematch policy. Defaults are chosen to be
    "production-reasonable" without yet being config-driven (Phase 5 will move
    these into system_configuration).
    """
    # Hard cap: pair counts at or above this within the recent window are
    # treated as forbidden by the solver unless no legal alternative exists.
    max_recent_matches_same_pair: int = 3

    # Per-occurrence penalty added to the harm score for every prior meeting
    # in the recent window.
    repeat_count_penalty: float = 250.0

    # Extra penalty if the pair has already appeared in the current session.
    same_session_penalty: float = 500.0

    # Phase / strategy weights — multiply the base harm by this factor. Critique
    # §17 expects DISCOVERY to weigh fresh opponents most heavily, TEAM_FORMAT
    # least (positional constraint dominates).
    phase_weight_discovery: float = 1.5
    phase_weight_transition: float = 1.0
    phase_weight_standard: float = 1.0
    phase_weight_tier_matched: float = 1.0
    phase_weight_cross_academy_only: float = 1.2
    phase_weight_team_format: float = 0.5
    phase_weight_full_round_robin: float = 0.5


# Module-level default policy. Tests and the engine use this until Phase 5
# wires fixture_config.py into the construction.
DEFAULT_POLICY = RematchPolicy()


@dataclass(frozen=True)
class RematchContext:
    """
    Inputs the caller (router) loads from the DB and passes into the engine.
    Keeping this immutable+frozen makes the policy auditable in tests.
    """
    # canonical (a, b) -> number of meetings within the recent window.
    recent_match_counts: dict = field(default_factory=dict)
    # canonical (a, b) -> True if the pair has already been scheduled this session.
    session_pairs: frozenset = field(default_factory=frozenset)


def harm_score(
    pair: tuple,
    ctx: RematchContext,
    *,
    phase_or_strategy: str = "STANDARD",
    policy: RematchPolicy = DEFAULT_POLICY,
) -> float:
    """
    Return the rematch harm score for `pair` (already canonical) in `ctx`.
    Higher = worse. The solver adds this to the gap-based base cost so
    non-rematch alternatives are preferred when they exist.
    """
    recent_n = ctx.recent_match_counts.get(pair, 0)
    base = recent_n * policy.repeat_count_penalty
    if pair in ctx.session_pairs:
        base += policy.same_session_penalty

    weight = _phase_weight(phase_or_strategy, policy)
    return base * weight


def is_forbidden(
    pair: tuple,
    ctx: RematchContext,
    *,
    policy: RematchPolicy = DEFAULT_POLICY,
) -> bool:
    """
    Hard cap: returns True if the pair has met `max_recent_matches_same_pair` or
    more times in the recent window. The solver treats forbidden edges as
    missing unless a fallback pass demands them.
    """
    return (
        ctx.recent_match_counts.get(pair, 0) >= policy.max_recent_matches_same_pair
    )


def _phase_weight(phase_or_strategy: str, policy: RematchPolicy) -> float:
    """Map the phase/strategy label to its rematch weight (critique §17)."""
    mapping = {
        "DISCOVERY": policy.phase_weight_discovery,
        "TRANSITION": policy.phase_weight_transition,
        "STANDARD": policy.phase_weight_standard,
        "TIER_MATCHED": policy.phase_weight_tier_matched,
        "CROSS_ACADEMY_ONLY": policy.phase_weight_cross_academy_only,
        "TEAM_FORMAT": policy.phase_weight_team_format,
        "FULL_ROUND_ROBIN": policy.phase_weight_full_round_robin,
    }
    return mapping.get(phase_or_strategy, 1.0)
