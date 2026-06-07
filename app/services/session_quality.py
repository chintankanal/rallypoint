"""
session_quality — compute fixture-quality metrics for intra-academy sessions.

Pure service (no DB access). Ports the TS fixtureAnalytics logic to Python,
including per-player stats, dimension calculations, applicability, weighted
scoring, and narrative generation.
"""
from dataclasses import dataclass
from typing import Optional
from schemas.session import SessionQuality, SessionQualityDimension, SessionQualityConstraints


# ── Phase-based weighting and verdict thresholds ────────────────────────────

PHASE_WEIGHTS = {
    "DISCOVERY": {
        "opponent-variety": 0.5,
        "game-equity": 0.2,
        "rest-distribution": 0.2,
        "competitive-balance": 0.1,
        "stretch-reach": 0.0,
    },
    "TRANSITION": {
        "opponent-variety": 0.3,
        "competitive-balance": 0.25,
        "stretch-reach": 0.2,
        "game-equity": 0.15,
        "rest-distribution": 0.1,
    },
    "STANDARD": {
        "competitive-balance": 0.3,
        "stretch-reach": 0.2,
        "opponent-variety": 0.2,
        "game-equity": 0.15,
        "rest-distribution": 0.15,
    },
}

VERDICT_THRESHOLDS = {
    "optimal": 0.85,
    "good": 0.65,
}

OVERALL_LABEL_THRESHOLDS = {
    "Strong": 85,
    "Good": 75,
    "Fair": 50,
}


@dataclass
class PlayerStats:
    player_id: str
    rating: float
    matches: int = 0
    unique_opponents: set = None
    byes: int = 0
    opponent_ratings: list = None
    stretching: int = 0
    anchoring: int = 0
    peer: int = 0
    tier: Optional[str] = None
    at_pool_ceiling: bool = False

    def __post_init__(self):
        if self.unique_opponents is None:
            self.unique_opponents = set()
        if self.opponent_ratings is None:
            self.opponent_ratings = []


def _get_verdict(ratio: float) -> str:
    """Classify ratio into verdict."""
    if ratio >= VERDICT_THRESHOLDS["optimal"]:
        return "optimal"
    elif ratio >= VERDICT_THRESHOLDS["good"]:
        return "good"
    return "limited"


def compute_session_quality(
    slots: list[dict],
    diagnostics: dict,
    *,
    phase: str = "STANDARD",
    num_tables: Optional[int] = None,
) -> Optional[SessionQuality]:
    """
    Compute quality report for a fixture session.

    Args:
        slots: List of fixture slot dicts with player_a, player_b, gap_band, etc.
        diagnostics: Dict with regime, competitive_max_gap, stretch_max_gap, etc.
        phase: Bootstrap phase (DISCOVERY|TRANSITION|STANDARD)
        num_tables: Optional number of tables in session

    Returns:
        SessionQuality with dimensions, scores, and narrative, or None if unavailable.
    """
    if not slots or not diagnostics:
        return None

    phase = phase or "STANDARD"
    phase_weights = PHASE_WEIGHTS.get(phase, PHASE_WEIGHTS["STANDARD"])
    stretch_max_gap = float(diagnostics.get("stretch_max_gap") or 250)
    competitive_max_gap = float(diagnostics.get("competitive_max_gap") or 150)

    # Collect player stats from slots
    player_stats = {}
    counts = {
        "bye": 0,
        "outOfBand": 0,
        "competitive": 0,
        "stretch": 0,
        "anchor": 0,
    }
    rounds = 0
    total_delta = 0
    delta_count = 0

    for slot in slots:
        rounds = max(rounds, slot.get("round_number", 0))

        if not slot.get("player_b"):
            # Bye slot
            pa = slot["player_a"]
            pid_a = pa["player_id"]
            if pid_a not in player_stats:
                player_stats[pid_a] = PlayerStats(
                    player_id=pid_a,
                    rating=float(pa.get("current_rating", 0)),
                    tier=pa.get("tier"),
                )
            player_stats[pid_a].byes += 1
            counts["bye"] += 1
            continue

        # Filled slot
        pa = slot["player_a"]
        pb = slot["player_b"]
        pid_a = pa["player_id"]
        pid_b = pb["player_id"]

        # Ensure both players in stats
        if pid_a not in player_stats:
            player_stats[pid_a] = PlayerStats(
                player_id=pid_a,
                rating=float(pa.get("current_rating", 0)),
                tier=pa.get("tier"),
            )
        if pid_b not in player_stats:
            player_stats[pid_b] = PlayerStats(
                player_id=pid_b,
                rating=float(pb.get("current_rating", 0)),
                tier=pb.get("tier"),
            )

        # Record match
        ps_a = player_stats[pid_a]
        ps_b = player_stats[pid_b]
        ps_a.matches += 1
        ps_b.matches += 1
        ps_a.unique_opponents.add(pid_b)
        ps_b.unique_opponents.add(pid_a)
        ps_a.opponent_ratings.append(float(pb.get("current_rating", 0)))
        ps_b.opponent_ratings.append(float(pa.get("current_rating", 0)))

        # Classify by gap_band
        gap_band = slot.get("gap_band", "unknown")
        if gap_band == "COMPETITIVE":
            counts["competitive"] += 1
        elif gap_band == "STRETCH":
            counts["stretch"] += 1
        elif gap_band == "ANCHOR":
            counts["anchor"] += 1
        elif gap_band == "OUT_OF_BAND":
            counts["outOfBand"] += 1

        # Track rating delta
        gap = abs(float(pa.get("current_rating", 0)) - float(pb.get("current_rating", 0)))
        total_delta += gap
        delta_count += 1

        # Record roles
        player_a_role = slot.get("player_a_role", "PEER").upper()
        player_b_role = slot.get("player_b_role", "PEER").upper()

        if "STRETCH" in player_a_role:
            ps_a.stretching += 1
        elif "ANCHOR" in player_a_role:
            ps_a.anchoring += 1
        else:
            ps_a.peer += 1

        if "STRETCH" in player_b_role:
            ps_b.stretching += 1
        elif "ANCHOR" in player_b_role:
            ps_b.anchoring += 1
        else:
            ps_b.peer += 1

    # Compute summary stats
    player_count = len(player_stats)
    parity_forces_bye = player_count % 2 == 1
    tightness_score = round(total_delta / delta_count, 1) if delta_count > 0 else 0
    total_slots = len(slots)
    bye_balanced = counts["bye"] == 0 or counts["bye"] <= 1
    filled_slots = max(0, total_slots - counts["bye"])

    # Compute per-player averages
    all_players = list(player_stats.values())
    matches_list = [p.matches for p in all_players]
    opponent_counts = [len(p.unique_opponents) for p in all_players]

    if matches_list:
        avg_matches = sum(matches_list) / len(matches_list)
    else:
        avg_matches = 0

    if opponent_counts:
        avg_unique_opponents = sum(opponent_counts) / len(opponent_counts)
    else:
        avg_unique_opponents = 0

    if matches_list:
        min_matches = min(matches_list)
        max_matches = max(matches_list)
    else:
        min_matches = max_matches = 0

    # Identify pool ceiling: a player is at pool ceiling iff no other player is
    # rated more than `competitive_max_gap` above them (no available stretch opponent).
    if all_players:
        for p in all_players:
            p.at_pool_ceiling = not any(
                o.player_id != p.player_id and o.rating > p.rating + competitive_max_gap
                for o in all_players
            )

    # Determine band-isolated players (no one within stretch_max_gap)
    isolated_ids = set()
    for p in all_players:
        has_nearby = any(
            other.player_id != p.player_id and abs(other.rating - p.rating) < stretch_max_gap
            for other in all_players
        )
        if not has_nearby:
            isolated_ids.add(p.player_id)

    # Count min achievable out-of-band (slots involving isolated players)
    min_achievable_out_of_band = sum(
        1 for slot in slots
        if slot.get("player_b")
        and (slot["player_a"]["player_id"] in isolated_ids
             or slot["player_b"]["player_id"] in isolated_ids)
    )
    excess_out_of_band = max(0, counts["outOfBand"] - min_achievable_out_of_band)

    # ── Dimension computations ────────────────────────────────────────────────

    # Stretch reach
    eligible_for_stretch = sum(1 for p in all_players if not p.at_pool_ceiling)
    achieved_stretch_count = sum(1 for p in all_players if p.stretching > 0)
    stretch_reach_ratio = (
        achieved_stretch_count / eligible_for_stretch
        if eligible_for_stretch > 0
        else 1.0
    )
    stretch_reach_applicable = eligible_for_stretch > 0
    stretch_reach_verdict = _get_verdict(stretch_reach_ratio)
    stretch_reach_limited_by = (
        "few higher-rated opponents in pool" if stretch_reach_ratio < 0.9 else None
    )
    stretch_reach_guidance = (
        "Expected for this group's rating spread — no action needed. "
        "To add play-up matches, invite higher-rated players."
        if stretch_reach_verdict == "limited"
        else None
    )

    # Competitive balance
    competitive_applicable = filled_slots > 0
    competitive_ratio = (
        max(0, min(1, 1 - excess_out_of_band / filled_slots))
        if filled_slots > 0
        else 1.0
    )
    competitive_verdict = _get_verdict(competitive_ratio)
    competitive_limited_by = (
        "wide rating spread forced some out-of-band pairings"
        if competitive_verdict == "limited"
        else None
    )
    competitive_guidance = (
        "Some matches exceeded the stretch band — split the pool by tier or add tables/rounds."
        if competitive_verdict == "limited"
        else None
    )
    competitive_achieved = (
        f"{counts['outOfBand']} out-of-band"
        f"{' (unavoidable)' if counts['outOfBand'] > 0 and excess_out_of_band == 0 else ''} "
        f"· avg gap {tightness_score} (within stretch band ≤{stretch_max_gap})"
    )

    # Opponent variety
    variety_ceiling = (
        min(rounds, max(0, player_count - 1)) if rounds > 0 else 0
    )
    variety_applicable = variety_ceiling > 0
    variety_denominator = max(1, variety_ceiling)
    variety_ratio = (
        min(1, avg_unique_opponents / variety_denominator) if rounds > 0 else 1.0
    )
    variety_verdict = _get_verdict(variety_ratio)
    variety_limited_by = (
        "small pool forces rematches across rounds" if variety_verdict == "limited" else None
    )
    variety_guidance = (
        "Pool is small relative to rounds, so some rematches are unavoidable — "
        "add players or reduce rounds for more variety."
        if variety_verdict == "limited"
        else None
    )
    variety_achieved = (
        f"{avg_unique_opponents:.1f} of {variety_ceiling} possible"
        if variety_applicable
        else "n/a"
    )

    # Game equity
    game_equity_applicable = max_matches > 0
    game_equity_ratio = (min_matches / max_matches) if max_matches > 0 else 1.0
    game_equity_verdict = _get_verdict(game_equity_ratio)
    game_equity_limited_by = (
        "table/round capacity yields uneven match counts"
        if game_equity_verdict == "limited"
        else None
    )
    game_equity_guidance = (
        "Uneven match counts from table/round capacity — add a table or adjust rounds."
        if game_equity_verdict == "limited"
        else None
    )
    game_equity_achieved = (
        f"all played {max_matches}"
        if min_matches == max_matches and max_matches > 0
        else f"min {min_matches} / max {max_matches}" if max_matches > 0
        else "n/a"
    )

    # Rest distribution
    unavoidable_byes = rounds if parity_forces_bye else 0
    byes_ratio = (
        1.0 if counts["bye"] <= unavoidable_byes
        else unavoidable_byes / counts["bye"] if counts["bye"] > 0
        else 1.0
    )
    byes_verdict = (
        "optimal" if counts["bye"] == unavoidable_byes
        else "good" if counts["bye"] <= unavoidable_byes + 1
        else "limited"
    )
    byes_limited_by = (
        "odd player count" if counts["bye"] > unavoidable_byes else None
    )
    byes_guidance = (
        "Odd player count forces a bye each round — add or drop a player for full pairing."
        if byes_verdict == "limited"
        else None
    )
    byes_achieved = f"{counts['bye']} of {unavoidable_byes} unavoidable bye{'s' if unavoidable_byes != 1 else ''}"

    # Build dimensions list
    dimensions = [
        SessionQualityDimension(
            key="competitive-balance",
            label="Competitive balance",
            achieved=competitive_achieved,
            ratio=max(0, min(1, competitive_ratio)),
            verdict=competitive_verdict,
            applicable=competitive_applicable,
            limited_by=competitive_limited_by,
            guidance=competitive_guidance,
        ),
        SessionQualityDimension(
            key="opponent-variety",
            label="Opponent variety",
            achieved=variety_achieved,
            ratio=max(0, min(1, variety_ratio)),
            verdict=variety_verdict,
            applicable=variety_applicable,
            limited_by=variety_limited_by,
            guidance=variety_guidance,
        ),
        SessionQualityDimension(
            key="game-equity",
            label="Game equity",
            achieved=game_equity_achieved,
            ratio=max(0, min(1, game_equity_ratio)),
            verdict=game_equity_verdict,
            applicable=game_equity_applicable,
            limited_by=game_equity_limited_by,
            guidance=game_equity_guidance,
        ),
        SessionQualityDimension(
            key="rest-distribution",
            label="Rest distribution",
            achieved=byes_achieved,
            ratio=max(0, min(1, byes_ratio)),
            verdict=byes_verdict,
            applicable=True,
            limited_by=byes_limited_by,
            guidance=byes_guidance,
        ),
        SessionQualityDimension(
            key="stretch-reach",
            label="Stretch reach",
            achieved=(
                f"{achieved_stretch_count} of {eligible_for_stretch} eligible "
                f"· {player_count - eligible_for_stretch} at pool ceiling"
                if stretch_reach_applicable
                else "n/a"
            ),
            ratio=max(0, min(1, stretch_reach_ratio)),
            verdict=stretch_reach_verdict,
            applicable=stretch_reach_applicable,
            limited_by=stretch_reach_limited_by,
            guidance=stretch_reach_guidance,
        ),
    ]

    # Compute weighted overall score
    applicable_dims = [d for d in dimensions if d.applicable]
    applicable_weight_sum = sum(phase_weights.get(d.key, 0) for d in applicable_dims)
    if applicable_weight_sum > 0:
        overall_score = round(
            (
                sum(
                    d.ratio * phase_weights.get(d.key, 0)
                    for d in applicable_dims
                )
                / applicable_weight_sum
            )
            * 100
        )
    else:
        overall_score = 50

    # Determine overall label
    overall_label = "Constrained"
    if overall_score >= OVERALL_LABEL_THRESHOLDS["Strong"]:
        overall_label = "Strong"
    elif overall_score >= OVERALL_LABEL_THRESHOLDS["Good"]:
        overall_label = "Good"
    elif overall_score >= OVERALL_LABEL_THRESHOLDS["Fair"]:
        overall_label = "Fair"

    # Generate narrative
    phase_intro = {
        "DISCOVERY": (
            "This is a discovery session — the goal is broad opponent exposure "
            "to settle ratings, not tight competitive balance."
        ),
        "TRANSITION": "This session balances rating discovery with competitive integrity.",
        "STANDARD": "This session emphasizes competitive integrity and stretch-band delivery.",
    }.get(phase, "")

    strengths = []
    if competitive_verdict == "optimal" and competitive_applicable:
        strengths.append("excellent competitive balance")
    if variety_verdict == "optimal" and variety_applicable:
        strengths.append("strong opponent variety")
    if game_equity_verdict == "optimal" and game_equity_applicable:
        strengths.append("strong game equity")
    if byes_verdict == "optimal":
        strengths.append("balanced rest distribution")

    limited_dims = [d for d in dimensions if d.applicable and d.verdict == "limited"]
    limiting_dim = None
    if limited_dims:
        with_reason = [d for d in limited_dims if d.limited_by]
        if with_reason:
            limiting_dim = min(with_reason, key=lambda d: d.ratio)
        else:
            limiting_dim = limited_dims[0]

    limiting_constraint = limiting_dim.limited_by if limiting_dim else None

    narrative = f"{phase_intro} Fixture quality is **{overall_label}**. "
    if strengths:
        narrative += f"Highlights: {', '.join(strengths)}. "
    if limited_dims:
        limited_names = ", ".join(d.label.lower() for d in limited_dims)
        if limiting_constraint:
            narrative += f"Limited by **{limiting_constraint}**: {limited_names} affected."
        else:
            narrative += f"Limited: {limited_names} affected."
    else:
        narrative += "Excellent fixture quality across all dimensions."

    # Build tier distribution from player stats
    tier_distribution = {}
    for ps in all_players:
        tier = ps.tier or "Unrated"
        tier_distribution[tier] = tier_distribution.get(tier, 0) + 1

    # Build constraints
    constraints = SessionQualityConstraints(
        player_count=player_count,
        parity_forces_bye=parity_forces_bye,
        raw_spread=diagnostics.get("raw_spread"),
        core_spread=diagnostics.get("core_spread"),
        tier_distribution=tier_distribution,
        provisional_count=diagnostics.get("provisional_count"),
        rounds=rounds,
        num_tables=num_tables,
        regime=diagnostics.get("regime"),
        competitive_max_gap=competitive_max_gap,
        stretch_max_gap=stretch_max_gap,
    )

    return SessionQuality(
        dimensions=dimensions,
        overall_score=overall_score,
        overall_label=overall_label,
        narrative=narrative,
        constraints=constraints,
    )
