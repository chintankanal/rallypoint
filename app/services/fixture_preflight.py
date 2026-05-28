"""
fixture_preflight — feasibility warnings for an upcoming fixture generation.

Per docs/fixture_engine_phased_impl_plan.md Phase 6 and critique §14, §15,
§16, certain pool shapes are *legal* but produce poor operator experiences
(dominant-academy BYE burden, odd-size tier islands, team-format roster
imbalance, lopsided tier capacity vs table count). Rather than fail
generation, this module returns a list of structured warnings the operator
sees inline before publishing.

Each warning is a dict:
    {
      "code":     str,    # stable identifier for the frontend (e.g. "DOMINANT_ACADEMY")
      "severity": str,    # "INFO" | "WARN" | "ERROR"
      "message":  str,    # human-readable text for the operator
      "context":  dict,   # structured details for logging or tooltips
    }

The module is pure Python with no DB access — the caller passes in the same
roster + capacity it will hand to the engine.
"""
from collections import Counter

# ── Warning codes ────────────────────────────────────────────────────────────

W_DOMINANT_ACADEMY = "DOMINANT_ACADEMY_BYE_BURDEN"
W_TEAM_FORMAT_IMBALANCE = "TEAM_FORMAT_LINEUP_IMBALANCE"
W_ODD_TIER_ISLAND = "ODD_TIER_ISLAND"
W_TIER_CAPACITY_SKEW = "TIER_CAPACITY_SKEW"
W_SMALL_POOL = "SMALL_POOL"

# Severity levels — frontend uses these to pick styling.
SEV_INFO = "INFO"
SEV_WARN = "WARN"
SEV_ERROR = "ERROR"


def _make(code: str, severity: str, message: str, **context) -> dict:
    return {"code": code, "severity": severity, "message": message, "context": context}


# ── Intra-academy session preflight ──────────────────────────────────────────

def preflight_session(
    players: list[dict],
    *,
    num_tables: int,
    matches_per_player_estimate: int,
) -> list[dict]:
    """
    Warnings for a single intra-academy session generation.

    Inputs:
      players: list of player dicts (player_id, current_rating, optional
        is_provisional / rated_matches_completed). Same shape the engine
        consumes.
      num_tables, matches_per_player_estimate: from calculate_session_capacity.
    """
    warnings: list[dict] = []

    n = len(players)
    if n < 4:
        warnings.append(_make(
            W_SMALL_POOL, SEV_WARN,
            f"Only {n} player(s) present — fixtures may be limited to a "
            "single round-robin with frequent BYEs.",
            player_count=n,
        ))
    elif n < 6:
        warnings.append(_make(
            W_SMALL_POOL, SEV_INFO,
            f"Small pool ({n} players) — running pure round-robin instead "
            "of phase-based pairing.",
            player_count=n,
        ))

    if matches_per_player_estimate == 0 and n >= 2:
        warnings.append(_make(
            "ZERO_CAPACITY", SEV_ERROR,
            "Session has zero capacity — too short for any match given the "
            "match format and table count.",
            num_tables=num_tables,
        ))

    return warnings


# ── Inter-academy event preflight ────────────────────────────────────────────

def preflight_event(
    players_by_academy: dict[str, list[dict]],
    *,
    strategy: str,
    num_tables: int,
    dominant_academy_threshold: float = 0.6,
    team_format_imbalance_threshold: float = 2.0,
    odd_tier_min_size: int = 3,
) -> list[dict]:
    """
    Warnings for an inter-academy event generation.

    Parameters with defaults are tunable knobs; production will route them
    from FixtureConfig in a later iteration. For now the defaults reflect
    operator-tested rules of thumb:

      - dominant_academy_threshold=0.6  : >= 60% of pool from one academy →
        CROSS_ACADEMY_ONLY can produce excessive BYEs (critique §14A, §15).
      - team_format_imbalance_threshold=2.0 : if the largest roster is >= 2x
        the smallest, TEAM_FORMAT benches a lot of the larger roster
        (critique §14B).
      - odd_tier_min_size=3 : odd-size tiers smaller than this warrant an
        odd-island warning (critique §14C, §16).
    """
    warnings: list[dict] = []

    sizes = {aid: len(ps) for aid, ps in players_by_academy.items()}
    total = sum(sizes.values())
    if total == 0:
        warnings.append(_make(
            "EMPTY_ROSTER", SEV_ERROR,
            "No players registered for this event yet.",
        ))
        return warnings

    # ── Dominant academy (CROSS_ACADEMY_ONLY) ──
    if strategy == "CROSS_ACADEMY_ONLY":
        for aid, n in sizes.items():
            frac = n / total
            if frac >= dominant_academy_threshold:
                warnings.append(_make(
                    W_DOMINANT_ACADEMY, SEV_WARN,
                    f"Academy {aid} holds {n}/{total} players ({frac:.0%}). "
                    "CROSS_ACADEMY_ONLY will produce many BYEs for this academy; "
                    "consider TIER_MATCHED or TEAM_FORMAT instead.",
                    academy_id=aid, academy_size=n, pool_size=total,
                    fraction=round(frac, 3),
                ))

    # ── Team format lineup imbalance ──
    if strategy == "TEAM_FORMAT":
        if len(sizes) >= 2:
            largest = max(sizes.values())
            smallest = min(sizes.values())
            if smallest > 0 and largest / smallest >= team_format_imbalance_threshold:
                warnings.append(_make(
                    W_TEAM_FORMAT_IMBALANCE, SEV_WARN,
                    f"Roster sizes vary widely (largest {largest}, smallest "
                    f"{smallest}). TEAM_FORMAT pairs positionally; surplus "
                    "players from the larger roster will receive BYEs.",
                    largest=largest, smallest=smallest,
                    ratio=round(largest / smallest, 2),
                ))

    # ── Odd-size tier islands (TIER_MATCHED) ──
    if strategy == "TIER_MATCHED":
        try:
            from app.utils.rating_math import get_tier, _load_config
            cfg = _load_config()
            tier_counts: Counter = Counter()
            for ps in players_by_academy.values():
                for p in ps:
                    tier_counts[get_tier(float(p["current_rating"]), cfg)] += 1
            for tier, count in tier_counts.items():
                if count > 0 and count < odd_tier_min_size and count % 2 == 1:
                    warnings.append(_make(
                        W_ODD_TIER_ISLAND, SEV_INFO,
                        f"Tier {tier} has {count} player(s) — odd-sized tiers "
                        "produce a rotating BYE every round and may merge "
                        "into an adjacent tier.",
                        tier=tier, count=count,
                    ))
        except Exception:
            # Don't fail preflight if tier lookup is unavailable.
            pass

    # ── Tier capacity vs table count (informational) ──
    if strategy == "TIER_MATCHED" and num_tables > 0:
        # Rough estimate: any tier whose simultaneous concurrent matches would
        # need more than num_tables triggers an info note.
        try:
            from app.utils.rating_math import get_tier, _load_config
            cfg = _load_config()
            tier_counts2: Counter = Counter()
            for ps in players_by_academy.values():
                for p in ps:
                    tier_counts2[get_tier(float(p["current_rating"]), cfg)] += 1
            for tier, count in tier_counts2.items():
                concurrent = count // 2
                if concurrent > num_tables:
                    warnings.append(_make(
                        W_TIER_CAPACITY_SKEW, SEV_INFO,
                        f"Tier {tier} has {count} players ({concurrent} "
                        f"concurrent pairs) — exceeds {num_tables} tables; "
                        "matches will run across multiple waves.",
                        tier=tier, concurrent_pairs=concurrent,
                        num_tables=num_tables,
                    ))
        except Exception:
            pass

    return warnings
