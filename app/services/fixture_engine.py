"""
Fixture engine: pure Python, zero DB access, fully unit-testable.

All functions accept and return plain dicts/lists of player dicts:
  player = {"player_id": str, "name": str, "current_rating": float}
  inter-academy players additionally carry: "academy_id": str, "academy_name": str

Returned slot dicts (per docs/fixture_engine_best_of_both_critique.md §2):
  {
    "round_number": int,
    "sub_round": str | None,   # "A" or "B" when two sub-rounds needed
    "table_number": int,
    "round_intent": str,       # COMPETITIVE | DEVELOPMENTAL  (round-level intent)
    "gap_band": str,           # COMPETITIVE | STRETCH | OUT_OF_BAND | BYE  (per-slot)
    "player_a_role": str,      # PEER | ANCHORING | STRETCHING | BYE
    "player_b_role": str,      # PEER | ANCHORING | STRETCHING | BYE
    "match_category": str,     # COMPETITIVE | STRETCH  (legacy compat field)
    "player_a_id": str,        # canonical: player_a_id < player_b_id
    "player_b_id": str | None, # None = BYE slot
    "expected_rating_gap": float,
    "fixture_strategy": str,
  }

The richer round_intent / gap_band / role fields are authoritative; match_category
is preserved as a compatibility field consumed by match_service and player_service.
Per the critique, downstream consumers should migrate to the richer fields in a
later phase.
"""
import math
from typing import Optional

# Match duration in minutes (not including 5-min changeover)
_MATCH_DURATION = {"BEST_OF_3": 20, "BEST_OF_5": 30, "BEST_OF_7": 40}
_CHANGEOVER = 5

# Gap thresholds. Critique §8 will move these into config in Phase 5; for now
# they remain module constants tied to the rating-eligible cap of 500 enforced
# by match_service.
_COMPETITIVE_MAX = 100   # gap ≤ 100 → COMPETITIVE
_STRETCH_MAX = 250       # gap 100 < x ≤ 250 → STRETCH
# Critique §2c: forced-exception pairings (singleton tiers, unsalvageable
# leftovers) may exceed STRETCH but must remain ≤ MAX_EXCEPTION_GAP. Beyond this
# cap the engine emits a BYE rather than a pairing match_service would reject as
# not-rating-eligible.
_MAX_EXCEPTION_GAP = 500

# Slot semantic vocabulary — keep aligned with sql/fixture_slot.sql enums.
_INTENT_COMPETITIVE = "COMPETITIVE"
_INTENT_DEVELOPMENTAL = "DEVELOPMENTAL"

_BAND_COMPETITIVE = "COMPETITIVE"
_BAND_STRETCH = "STRETCH"
_BAND_OUT_OF_BAND = "OUT_OF_BAND"
_BAND_BYE = "BYE"

_ROLE_PEER = "PEER"
_ROLE_ANCHORING = "ANCHORING"
_ROLE_STRETCHING = "STRETCHING"
_ROLE_BYE = "BYE"

# Sessions smaller than this fall through to pure round-robin per the design
# (see docs/jlrs_fixtures_design and critique §19).
_SMALL_SESSION_PLAYER_COUNT = 6


# ── Phase detection ───────────────────────────────────────────────────────────

def detect_phase(players: list[dict]) -> str:
    """
    Phase boundaries per docs/jlrs_fixtures_design and critique §18:

      DISCOVERY  : spread ≤ 100
      TRANSITION : 100 < spread ≤ 250
      STANDARD   : spread > 250
    """
    if len(players) < 2:
        return "DISCOVERY"
    ratings = [float(p["current_rating"]) for p in players]
    spread = max(ratings) - min(ratings)
    if spread <= 100:
        return "DISCOVERY"
    if spread <= 250:
        return "TRANSITION"
    return "STANDARD"


def rating_spread(players: list[dict]) -> float:
    if len(players) < 2:
        return 0.0
    ratings = [float(p["current_rating"]) for p in players]
    return max(ratings) - min(ratings)


# ── Session capacity ──────────────────────────────────────────────────────────

def calculate_session_capacity(
    session_minutes: int,
    num_tables: int,
    match_format: str,
    num_players: int,
) -> dict:
    """
    Returns capacity dict including num_rounds (rounds to generate) and
    matches_per_player (reporting metric, capped at 4).

    num_rounds uses pairs_per_round = num_players // 2 so odd-count groups
    (which have 1 BYE per round) get the correct number of rounds from the
    available time — e.g. 7 players / 3 tables / 120 min Bo3 → 4 rounds, not 3.
    """
    duration = _MATCH_DURATION.get(match_format.upper(), 20)
    slot_time = duration + _CHANGEOVER
    matches_per_table = math.floor(session_minutes / slot_time)
    total_slots = matches_per_table * num_tables
    matches_per_player = min(4, math.floor(total_slots * 2 / num_players)) if num_players > 0 else 0
    pairs_per_round = num_players // 2  # integer div handles odd counts (BYE slot)
    num_rounds = min(4, math.floor(total_slots / pairs_per_round)) if pairs_per_round > 0 else 0
    return {
        "matches_per_table": matches_per_table,
        "total_slots": total_slots,
        "matches_per_player": matches_per_player,
        "num_rounds": num_rounds,
    }


# ── Canonical ordering helper ─────────────────────────────────────────────────

def _canonical(pid_a: str, pid_b: str) -> tuple[str, str]:
    return (pid_a, pid_b) if pid_a < pid_b else (pid_b, pid_a)


def _gap(players_by_id: dict, pid_a: str, pid_b: str) -> float:
    return abs(
        float(players_by_id[pid_a]["current_rating"])
        - float(players_by_id[pid_b]["current_rating"])
    )


def _classify_gap(gap: float) -> str:
    """Map a rating gap to its gap_band label (per-slot, derived from gap only)."""
    if gap <= _COMPETITIVE_MAX:
        return _BAND_COMPETITIVE
    if gap <= _STRETCH_MAX:
        return _BAND_STRETCH
    return _BAND_OUT_OF_BAND


def _legacy_match_category(band: str) -> str:
    """
    Compatibility mapping (critique §2): downstream consumers still read the
    match_category enum {COMPETITIVE, STRETCH, ANCHOR}. We never emit ANCHOR
    here because the legacy semantics conflate the two players' perspectives;
    use player_a_role / player_b_role for the richer view.
    """
    if band == _BAND_COMPETITIVE or band == _BAND_BYE:
        return "COMPETITIVE"
    return "STRETCH"


def _derive_roles(
    round_intent: str,
    gap_band: str,
    players_by_id: dict,
    canon_a: str,
    canon_b: str | None,
) -> tuple[str, str]:
    """
    Per critique §2 / docs/jlrs_fixtures_design §22, role semantics:
      - BYE: present player is PEER, absent slot is BYE
      - competitive intent + competitive gap: both PEER
      - developmental intent OR cross-band gap: higher-rated ANCHORING,
        lower-rated STRETCHING
    """
    if canon_b is None:
        return _ROLE_PEER, _ROLE_BYE
    if round_intent == _INTENT_COMPETITIVE and gap_band == _BAND_COMPETITIVE:
        return _ROLE_PEER, _ROLE_PEER
    rating_a = float(players_by_id[canon_a]["current_rating"])
    rating_b = float(players_by_id[canon_b]["current_rating"])
    if rating_a >= rating_b:
        return _ROLE_ANCHORING, _ROLE_STRETCHING
    return _ROLE_STRETCHING, _ROLE_ANCHORING


def _build_slot(
    *,
    round_number: int,
    table_number: int,
    sub_round: str | None,
    round_intent: str,
    players_by_id: dict,
    player_a_id: str,
    player_b_id: str | None,
    fixture_strategy: str,
) -> dict:
    """
    Construct a fully-populated slot dict including additive fields
    (round_intent, gap_band, player_a_role, player_b_role) and the legacy
    match_category for compatibility with downstream consumers.

    All slot construction in this module must flow through this helper so the
    invariants in tests/unit/test_fixture_engine.py (Phase 1) stay enforced.
    """
    if player_b_id is None:
        return {
            "round_number": round_number,
            "sub_round": sub_round,
            "table_number": table_number,
            "round_intent": round_intent,
            "gap_band": _BAND_BYE,
            "player_a_role": _ROLE_PEER,
            "player_b_role": _ROLE_BYE,
            "match_category": _legacy_match_category(_BAND_BYE),
            "player_a_id": player_a_id,
            "player_b_id": None,
            "expected_rating_gap": 0.0,
            "fixture_strategy": fixture_strategy,
        }

    canon_a, canon_b = _canonical(player_a_id, player_b_id)
    gap = _gap(players_by_id, canon_a, canon_b)
    band = _classify_gap(gap)
    role_a, role_b = _derive_roles(round_intent, band, players_by_id, canon_a, canon_b)
    return {
        "round_number": round_number,
        "sub_round": sub_round,
        "table_number": table_number,
        "round_intent": round_intent,
        "gap_band": band,
        "player_a_role": role_a,
        "player_b_role": role_b,
        "match_category": _legacy_match_category(band),
        "player_a_id": canon_a,
        "player_b_id": canon_b,
        "expected_rating_gap": round(gap, 2),
        "fixture_strategy": fixture_strategy,
    }


# ── Table assignment ──────────────────────────────────────────────────────────

def _assign_tables(
    pairs: list[tuple[Optional[str], Optional[str]]],
    num_tables: int,
    round_number: int,
    round_intent: str,
    players_by_id: dict,
    strategy: str = "TIER_MATCHED",
) -> list[dict]:
    """
    Assign pairs to tables. If more pairs than tables, split into sub-rounds A/B
    (a multi-wave numeric scheduler is on the Phase 3 roadmap; until then sub_round
    remains the 2-wave A/B label for the intra-academy DDL).

    `round_intent` is the round-level COMPETITIVE / DEVELOPMENTAL label; the
    per-slot gap_band is derived inside _build_slot from the actual rating gap.
    """
    slots: list[dict] = []
    if not pairs:
        return slots

    needs_subrounds = len(pairs) > num_tables

    for i, (pid_a, pid_b) in enumerate(pairs):
        sub = ("A" if i < num_tables else "B") if needs_subrounds else None
        table = (i % num_tables) + 1
        if pid_a is None and pid_b is None:
            # Defensive: never emit a fully-empty slot.
            continue
        if pid_a is None or pid_b is None:
            active_id = pid_a if pid_a is not None else pid_b
            slots.append(_build_slot(
                round_number=round_number,
                table_number=table,
                sub_round=sub,
                round_intent=round_intent,
                players_by_id=players_by_id,
                player_a_id=active_id,
                player_b_id=None,
                fixture_strategy=strategy,
            ))
            continue
        slots.append(_build_slot(
            round_number=round_number,
            table_number=table,
            sub_round=sub,
            round_intent=round_intent,
            players_by_id=players_by_id,
            player_a_id=pid_a,
            player_b_id=pid_b,
            fixture_strategy=strategy,
        ))
    return slots


# ── Phase A: Discovery (circle-method round-robin) ────────────────────────────

def _circle_round(players: list[dict], round_idx: int) -> list[tuple]:
    """
    Return pairs for round_idx (0-indexed) using the standard circle method.
    Critique §20: ordering is normalized by player_id so identical pools
    produce identical schedules regardless of caller input order.
    Odd N is handled by appending a BYE sentinel (None).
    """
    ps = sorted(players, key=lambda p: p["player_id"])
    has_bye = len(ps) % 2 == 1
    if has_bye:
        ps = ps + [None]  # BYE sentinel

    n = len(ps)
    fixed = ps[0]
    rotating = list(ps[1:])          # length n-1

    # Rotate right by round_idx (last element moves to front)
    r = round_idx % (n - 1)
    rotating = rotating[-(r):] + rotating[:-(r)] if r else rotating

    pairs = [(fixed, rotating[-1])]
    mid = (n - 2) // 2
    for i in range(mid):
        pairs.append((rotating[i], rotating[-2 - i]))

    # Unwrap: players are dicts, BYE is None
    return [
        (
            a["player_id"] if a is not None else None,
            b["player_id"] if b is not None else None,
        )
        for a, b in pairs
    ]


def generate_discovery_fixtures(
    players: list[dict],
    round_offset: int,
    matches_per_player: int,
    num_tables: int,
) -> list[dict]:
    """
    Round-robin via circle method.
    round_offset = number of rounds already played for this event (from prior sessions).
    Produces matches_per_player rounds starting at round_offset.
    All matches are COMPETITIVE intent; the per-slot gap_band reflects the
    actual rating gap, which is typically COMPETITIVE in a discovery pool.
    """
    players_by_id = {p["player_id"]: p for p in players}
    n = len(players)
    if n < 2:
        return []
    total_rounds = (n if n % 2 == 1 else n - 1)  # full round-robin cycle

    slots: list[dict] = []
    for step in range(matches_per_player):
        round_idx = (round_offset + step) % total_rounds
        pairs = _circle_round(players, round_idx)
        round_number = round_offset + step + 1
        slots.extend(
            _assign_tables(pairs, num_tables, round_number, _INTENT_COMPETITIVE, players_by_id)
        )
    return slots


# ── Phase B: Transition (median split) ───────────────────────────────────────

def _half_round_pairs(half_pids: list[str], round_idx: int) -> list[tuple]:
    """
    Legal one-match-per-player pairing inside a half via the circle method.
    Returns canonical (a, b) tuples with (pid, None) for BYE when the half is
    odd-sized. Empty input returns []. Single-player input returns [(pid, None)].

    Critique §1: the old within_half_pairs used a sliding window that placed
    interior players in multiple pairs in the same round. The circle method
    guarantees each player appears in exactly one pair per round.

    The rotation is chosen so that round_idx=0 yields adjacent pairs
    (smallest gaps) in a rating-sorted half — preserving the transition-phase
    design intent that the first competitive round is tightest.
    """
    if not half_pids:
        return []
    if len(half_pids) == 1:
        return [(half_pids[0], None)]

    ps: list = list(half_pids)
    if len(ps) % 2 == 1:
        ps = ps + [None]  # BYE sentinel
    n = len(ps)
    total_rotations = n - 1
    # Map round_idx=0 to the rotation that yields adjacent pairs.
    r = (total_rotations - 1 - round_idx) % total_rotations
    fixed = ps[0]
    rotating = list(ps[1:])
    if r:
        rotating = rotating[-r:] + rotating[:-r]
    pairs: list[tuple] = [(fixed, rotating[-1])]
    mid = (n - 2) // 2
    for i in range(mid):
        pairs.append((rotating[i], rotating[-2 - i]))
    return pairs


def _cross_half_pairs(upper_pids: list[str], lower_pids: list[str], round_idx: int) -> list[tuple]:
    """
    Fold-pair top of upper half with top of lower half (rotated by round_idx).
    The spare player (when total count is odd) receives an explicit BYE so
    every attending player is accounted for (critique §1).
    """
    if not upper_pids or not lower_pids:
        spare = (upper_pids or lower_pids)[:]
        return [(p, None) for p in spare]

    # Rotate the upper half so successive stretch rounds yield different folds.
    n_upper = len(upper_pids)
    r = round_idx % n_upper if n_upper else 0
    rotated_upper = upper_pids[r:] + upper_pids[:r] if r else upper_pids

    pairs: list[tuple] = []
    paired: set[str] = set()
    fold_len = min(len(rotated_upper), len(lower_pids))
    for i in range(fold_len):
        a = rotated_upper[i]
        b = lower_pids[i]
        pairs.append((a, b))
        paired.add(a)
        paired.add(b)
    for pid in upper_pids + lower_pids:
        if pid not in paired:
            pairs.append((pid, None))  # explicit BYE for the spare
    return pairs


def generate_transition_fixtures(
    players: list[dict],
    matches_per_player: int,
    num_tables: int,
    round_offset: int = 0,
) -> list[dict]:
    """
    Sort by rating desc and split at the median. Competitive rounds pair
    within each half via circle-method round-robin; stretch rounds fold
    upper-half top vs lower-half top.

    Critique #1 fix: legal one-match-per-player rounds.
    Critique #12 fix: round_offset shifts numbering so multi-session events
    have a stable global round counter.
    """
    if len(players) < 2:
        return []
    sorted_players = sorted(players, key=lambda p: float(p["current_rating"]), reverse=True)
    players_by_id = {p["player_id"]: p for p in players}
    n = len(sorted_players)
    mid = n // 2
    upper_pids = [p["player_id"] for p in sorted_players[:mid]]
    lower_pids = [p["player_id"] for p in sorted_players[mid:]]  # may be longer on odd N

    slots: list[dict] = []
    competitive_done = 0  # shift counter for within-half rounds
    stretch_done = 0      # shift counter for cross-half rounds

    for step in range(matches_per_player):
        round_number = round_offset + step + 1
        is_stretch_round = (step == 1)  # round 2 (index 1) is the stretch round

        if is_stretch_round:
            pairs = _cross_half_pairs(upper_pids, lower_pids, stretch_done)
            stretch_done += 1
            slots.extend(_assign_tables(
                pairs, num_tables, round_number, _INTENT_DEVELOPMENTAL, players_by_id
            ))
        else:
            shift = competitive_done
            pairs_upper = _half_round_pairs(upper_pids, shift)
            pairs_lower = _half_round_pairs(lower_pids, shift)
            competitive_done += 1
            slots.extend(_assign_tables(
                pairs_upper + pairs_lower, num_tables, round_number,
                _INTENT_COMPETITIVE, players_by_id,
            ))

    return slots


# ── Phase C: Standard (full competitive + folded stretch) ─────────────────────

def generate_standard_fixtures(
    players: list[dict],
    recent_match_pairs: set[tuple],
    matches_per_player: int,
    num_tables: int,
    round_offset: int = 0,
) -> list[dict]:
    """
    Standard algorithm:
    - Competitive rounds: adjacent pairing within tier (intent=COMPETITIVE)
    - Stretch round (round 2): folded pairing k vs k + floor(N/4), gap filter
      100-250 (intent=DEVELOPMENTAL)
    - BYE for odd player count (rotating)
    - recent_match_pairs: canonical (a,b) pairs to exclude from stretch round
    - round_offset: shifts emitted round numbers so multi-session events keep
      a stable global counter (critique #12).

    Out-of-band leftover pairings (gap > 250) are no longer silently labeled
    STRETCH — _build_slot derives gap_band=OUT_OF_BAND from the actual gap
    (critique #3). Pairings beyond _MAX_EXCEPTION_GAP are converted to BYEs.
    """
    from app.utils.rating_math import get_tier, _load_config

    cfg = _load_config()
    sorted_players = sorted(players, key=lambda p: float(p["current_rating"]), reverse=True)
    players_by_id = {p["player_id"]: p for p in players}
    n = len(sorted_players)
    pids = [p["player_id"] for p in sorted_players]

    # Group by tier
    def tier_groups() -> list[list[str]]:
        groups: list[list[str]] = []
        current_tier = None
        current_group: list[str] = []
        for pid in pids:
            t = get_tier(float(players_by_id[pid]["current_rating"]), cfg)
            if t != current_tier:
                if current_group:
                    groups.append(current_group)
                current_tier = t
                current_group = [pid]
            else:
                current_group.append(pid)
        if current_group:
            groups.append(current_group)
        return groups

    def competitive_pairs(shift: int, bye_rotation: int = 0) -> list[tuple]:
        """Adjacent within-tier pairing. shift=0 → (0,1),(2,3)... shift=1 → cross-half pairing."""
        groups = tier_groups()
        pairs: list[tuple] = []
        leftovers: list[str] = []

        for group in groups:
            gn = len(group)
            if shift == 0:
                for i in range(0, gn - 1, 2):
                    pairs.append((group[i], group[i + 1]))
                if gn % 2 == 1:
                    leftovers.append(group[-1])
            else:
                if gn >= 4:
                    # Cross-half: (0, half), (1, half+1), ...
                    # gn=4 → (0,2),(1,3). gn=6 → (0,3),(1,4),(2,5). All covered.
                    half = gn // 2
                    for i in range(half):
                        pairs.append((group[i], group[i + half]))
                    if gn % 2 == 1:
                        leftovers.append(group[-1])
                else:
                    # Small group (gn=2 or 3): rotate by shift so each competitive
                    # round produces a different pair.
                    # gn=3 over 3 shifts: (A,B)C → (B,C)A → (A,C)B — full round-robin.
                    rot = shift % gn
                    rotated = group[rot:] + group[:rot]
                    for i in range(0, len(rotated) - 1, 2):
                        pairs.append((rotated[i], rotated[i + 1]))
                    if len(rotated) % 2 == 1:
                        leftovers.append(rotated[-1])

        # Rotate leftover list so BYE cycles through players across competitive rounds.
        if leftovers and bye_rotation > 0:
            rot = bye_rotation % len(leftovers)
            leftovers = leftovers[rot:] + leftovers[:rot]

        # Critique §3: pair leftovers by rating proximity rather than by list
        # order. Apply a soft rematch-avoidance preference (two-pass): first try
        # partners not in recent_match_pairs ∪ session_pairs; only if no such
        # partner exists within _MAX_EXCEPTION_GAP do we fall back to a recent
        # one. Gaps > _MAX_EXCEPTION_GAP convert to BYE so the rating engine
        # never sees a non-eligible pairing. _build_slot labels gaps in
        # (_STRETCH_MAX, _MAX_EXCEPTION_GAP] as gap_band=OUT_OF_BAND.
        leftover_pids = sorted(
            leftovers, key=lambda pid: float(players_by_id[pid]["current_rating"]),
            reverse=True,
        )
        soft_exclude = recent_match_pairs | session_pairs
        used: set[str] = set()
        for i, pid_a in enumerate(leftover_pids):
            if pid_a in used:
                continue
            # Pass 1: closest partner that is NOT a recent rematch.
            best_partner: str | None = None
            best_gap: float = float("inf")
            for pid_b in leftover_pids[i + 1:]:
                if pid_b in used:
                    continue
                if _canonical(pid_a, pid_b) in soft_exclude:
                    continue
                g = _gap(players_by_id, pid_a, pid_b)
                if g < best_gap:
                    best_gap = g
                    best_partner = pid_b
            # Pass 2 (fallback): no non-rematch within reach → allow recent.
            if best_partner is None or best_gap > _MAX_EXCEPTION_GAP:
                fb_partner: str | None = None
                fb_gap = float("inf")
                for pid_b in leftover_pids[i + 1:]:
                    if pid_b in used:
                        continue
                    g = _gap(players_by_id, pid_a, pid_b)
                    if g < fb_gap:
                        fb_gap = g
                        fb_partner = pid_b
                if fb_partner is not None and fb_gap <= _MAX_EXCEPTION_GAP and (
                    best_partner is None or fb_gap < best_gap
                ):
                    best_partner, best_gap = fb_partner, fb_gap
            if best_partner is not None and best_gap <= _MAX_EXCEPTION_GAP:
                pairs.append((pid_a, best_partner))
                used.add(pid_a)
                used.add(best_partner)
            else:
                # No acceptable opponent within the exception cap → BYE.
                pairs.append((pid_a, None))
                used.add(pid_a)

        return pairs

    def stretch_pairs(
        priority_pid: str | None = None,
        extra_exclude: set[tuple] | None = None,
    ) -> list[tuple]:
        """
        Folded: player at rank k pairs with rank k + floor(N/4).
        Gap filter: < 100 → skip (too close), > 250 → skip (find closer).
        Exclude recent_match_pairs and extra_exclude (pairs already played
        this session, to prevent stretch round repetition — Bug 4 fix).
        priority_pid: given first pick before the greedy sweep so the
        sweep doesn't exhaust their valid partners first (prevents a player
        who already had a BYE from being blocked by higher-rated peers).
        """
        fold = max(1, math.floor(n / 4))
        used: set[str] = set()
        pairs: list[tuple] = []
        all_exclude = recent_match_pairs | (extra_exclude or set())

        # Priority pass: give last BYE player first pick of stretch partners.
        # `pids` is sorted by rating desc, so gap to pid_a is monotonically
        # non-decreasing as offset increases. Once gap > _STRETCH_MAX, no
        # later candidate in this direction can be legal (critique §10).
        if priority_pid is not None and priority_pid in pids:
            k = pids.index(priority_pid)
            for offset in range(fold, n - k):
                pid_b = pids[k + offset]
                gap = _gap(players_by_id, priority_pid, pid_b)
                if gap > _STRETCH_MAX:
                    break  # short-circuit: gap only grows from here
                if pid_b in used:
                    continue
                canon = _canonical(priority_pid, pid_b)
                if canon in all_exclude:
                    continue
                if gap >= _COMPETITIVE_MAX:
                    pairs.append(canon)
                    used.add(priority_pid)
                    used.add(pid_b)
                    break

        for k in range(n - fold):
            pid_a = pids[k]
            if pid_a in used:
                continue

            for offset in range(fold, n - k):
                pid_b = pids[k + offset]
                gap = _gap(players_by_id, pid_a, pid_b)
                if gap > _STRETCH_MAX:
                    break  # short-circuit: gap monotonic, no closer candidate later
                if pid_b in used:
                    continue
                canon = _canonical(pid_a, pid_b)
                if canon in all_exclude:
                    continue
                if gap < _COMPETITIVE_MAX:
                    continue
                pairs.append(canon)
                used.add(pid_a)
                used.add(pid_b)
                break

        return pairs

    # Choose round pattern based on tier composition.
    #
    # C-S-C-S  (Variety Maximization): all tier groups have even player counts.
    #   Steps: 0→C, 1→S, 2→C, 3→S  (stretch = odd step)
    #   Rationale: even-sized groups are fully paired in one competitive round, so
    #   alternating provides maximum variety.
    #
    # C-C-S-C  (Rotation Completion): at least one tier group has an odd count.
    #   Steps: 0→C, 1→C, 2→S, 3→C  (stretch = step 2 only)
    #   Rationale: a 3-player tier needs 3 competitive rounds (shifts 0, 1, 2) to
    #   complete its internal round-robin. C-S-C-S only provides 2, leaving one
    #   intra-tier pair unplayed. C-C-S-C fulfils the 3-round requirement while
    #   still delivering a stretch round.
    initial_groups = tier_groups()
    has_odd_tier = any(len(g) % 2 == 1 for g in initial_groups)

    slots: list[dict] = []
    competitive_shift = 0
    last_bye_pid: str | None = None
    session_pairs: set[tuple] = set()  # Bug 4: track pairs already played this session

    for step in range(matches_per_player):
        round_number = round_offset + step + 1  # critique #12: honor round_offset
        is_stretch = (step == 2) if has_odd_tier else (step % 2 == 1)

        if is_stretch:
            pairs = stretch_pairs(priority_pid=last_bye_pid, extra_exclude=session_pairs)

            # Critique §3 + §6: any player still unpaired after the strict
            # 100–250 sweep gets matched to their nearest available partner via
            # rating-proximity nearest-neighbor. Pairings whose gap exceeds
            # _MAX_EXCEPTION_GAP fall back to BYE rather than create matches
            # the rating engine would reject. _build_slot will label gaps in
            # (_STRETCH_MAX, _MAX_EXCEPTION_GAP] as gap_band=OUT_OF_BAND.
            paired_ids = {pid for pair in pairs for pid in pair if pid is not None}
            unpaired = [pid for pid in pids if pid not in paired_ids]
            unpaired.sort(
                key=lambda pid: float(players_by_id[pid]["current_rating"]),
                reverse=True,
            )
            used: set[str] = set()
            for i, pid_a in enumerate(unpaired):
                if pid_a in used:
                    continue
                best_partner: str | None = None
                best_gap = float("inf")
                for pid_b in unpaired[i + 1:]:
                    if pid_b in used:
                        continue
                    g = _gap(players_by_id, pid_a, pid_b)
                    if g < best_gap:
                        best_gap = g
                        best_partner = pid_b
                if best_partner is not None and best_gap <= _MAX_EXCEPTION_GAP:
                    pairs.append(_canonical(pid_a, best_partner))
                    used.add(pid_a)
                    used.add(best_partner)
                else:
                    pairs.append((pid_a, None))
                    used.add(pid_a)

            slots.extend(_assign_tables(
                pairs, num_tables, round_number, _INTENT_DEVELOPMENTAL, players_by_id
            ))
        else:
            pairs = competitive_pairs(competitive_shift, bye_rotation=competitive_shift)
            bye_list = [p[0] for p in pairs if p[1] is None]
            last_bye_pid = bye_list[0] if bye_list else None
            slots.extend(_assign_tables(
                pairs, num_tables, round_number, _INTENT_COMPETITIVE, players_by_id
            ))
            competitive_shift += 1

        # Bug 4: record pairs played this round for stretch dedup
        for pair in pairs:
            if pair[0] is not None and pair[1] is not None:
                session_pairs.add(_canonical(pair[0], pair[1]))

    return slots


# ── Dispatcher ────────────────────────────────────────────────────────────────

def generate_fixtures(
    players: list[dict],
    recent_match_pairs: set[tuple],
    round_offset: int,
    session_minutes: int,
    num_tables: int,
    match_format: str,
) -> dict:
    """
    Main entry point. Returns:
    {
      "phase": str,
      "spread": float,
      "matches_per_player": int,
      "slots": list[dict],
    }
    """
    spread = rating_spread(players)
    capacity = calculate_session_capacity(
        session_minutes, num_tables, match_format, len(players)
    )
    num_rounds = capacity["num_rounds"]  # Bug 1 fix: use round count, not per-player count
    mpp = capacity["matches_per_player"]

    # Critique §19: small sessions skip phase-based heuristics entirely and run a
    # pure round-robin (discovery generator). Phase is still reported truthfully
    # so callers don't see DISCOVERY when the spread says otherwise.
    if len(players) < _SMALL_SESSION_PLAYER_COUNT:
        phase = detect_phase(players)
        if num_rounds == 0:
            return {"phase": phase, "spread": spread, "matches_per_player": 0, "slots": []}
        slots = generate_discovery_fixtures(players, round_offset, num_rounds, num_tables)
        return {"phase": phase, "spread": spread, "matches_per_player": mpp, "slots": slots}

    phase = detect_phase(players)
    if num_rounds == 0:
        return {"phase": phase, "spread": spread, "matches_per_player": 0, "slots": []}

    if phase == "DISCOVERY":
        slots = generate_discovery_fixtures(players, round_offset, num_rounds, num_tables)
    elif phase == "TRANSITION":
        slots = generate_transition_fixtures(
            players, num_rounds, num_tables, round_offset=round_offset,
        )
    else:
        slots = generate_standard_fixtures(
            players, recent_match_pairs, num_rounds, num_tables, round_offset=round_offset,
        )

    return {
        "phase": phase,
        "spread": spread,
        "matches_per_player": mpp,
        "slots": slots,
    }


# ── Inter-academy League Fixture Engine ───────────────────────────────────────

def _interleave_academies(players_by_academy: dict[str, list[dict]]) -> list[dict]:
    """
    Interleave players from different academies so the circle method produces
    cross-academy pairings. Academy with the most players listed first (reduces BYEs).
    Players within each academy are expected pre-sorted by rating desc.
    """
    sorted_lists = sorted(players_by_academy.values(), key=len, reverse=True)
    max_len = max(len(p) for p in sorted_lists) if sorted_lists else 0
    result: list[dict] = []
    for i in range(max_len):
        for players in sorted_lists:
            if i < len(players):
                result.append(players[i])
    return result


def _circle_pairs_for_ids(pids: list, round_idx: int) -> list[tuple]:
    """
    Circle method on a flat list of player_ids (None = BYE sentinel).
    List must have even length. Returns pairs for one round.
    """
    n = len(pids)
    fixed = pids[0]
    rotating = list(pids[1:])
    r = round_idx % (n - 1)
    if r:
        rotating = rotating[-r:] + rotating[:-r]
    pairs: list[tuple] = [(fixed, rotating[-1])]
    mid = (n - 2) // 2
    for i in range(mid):
        pairs.append((rotating[i], rotating[-2 - i]))
    return pairs


def _swap_for_novelty(
    pairs: list[tuple],
    played_pairs: set[tuple],
) -> list[tuple]:
    """
    Single-pass swap: for each pair that appears in played_pairs (rematch from prior
    event), try to find another pair to swap partners with that reduces total rematches.

    Used by FULL_ROUND_ROBIN where there are no academy constraints. Strategies
    that must preserve cross-academy invariants (CROSS_ACADEMY_ONLY, TIER_MATCHED)
    must use _swap_for_novelty_constrained instead.
    """
    pairs = list(pairs)
    for i in range(len(pairs)):
        a, b = pairs[i]
        if b is None or _canonical(a, b) not in played_pairs:
            continue
        for j in range(len(pairs)):
            if i == j:
                continue
            c, d = pairs[j]
            if d is None:
                continue
            old_score = (
                (1 if _canonical(a, b) in played_pairs else 0)
                + (1 if _canonical(c, d) in played_pairs else 0)
            )
            new_score = (
                (1 if _canonical(a, d) in played_pairs else 0)
                + (1 if _canonical(c, b) in played_pairs else 0)
            )
            if new_score < old_score:
                pairs[i] = (a, d)
                pairs[j] = (c, b)
                break
    return pairs


def _swap_for_novelty_constrained(
    pairs: list[tuple],
    played_pairs: set[tuple],
    players_by_id: dict,
) -> list[tuple]:
    """
    Critique #4: constraint-aware novelty swap. Only swaps when both replacement
    pairs remain cross-academy and the rematch count strictly decreases. Used
    by strategies that promise no same-academy matches.

    A swap is accepted iff:
      - both new pairs satisfy academy_a != academy_b
      - the rematch count after the swap is strictly lower than before
    """
    pairs = list(pairs)
    for i in range(len(pairs)):
        a, b = pairs[i]
        if b is None or _canonical(a, b) not in played_pairs:
            continue
        acad_ai = players_by_id[a]["academy_id"]
        acad_bi = players_by_id[b]["academy_id"]
        for j in range(len(pairs)):
            if i == j:
                continue
            c, d = pairs[j]
            if d is None:
                continue
            acad_cj = players_by_id[c]["academy_id"]
            acad_dj = players_by_id[d]["academy_id"]
            # Replacement pairs (a, d) and (c, b) must both stay cross-academy.
            if acad_ai == acad_dj or acad_cj == acad_bi:
                continue
            old_score = (
                (1 if _canonical(a, b) in played_pairs else 0)
                + (1 if _canonical(c, d) in played_pairs else 0)
            )
            new_score = (
                (1 if _canonical(a, d) in played_pairs else 0)
                + (1 if _canonical(c, b) in played_pairs else 0)
            )
            if new_score < old_score:
                pairs[i] = (a, d)
                pairs[j] = (c, b)
                break
    return pairs


def _assign_tables_league(
    pairs: list[tuple],
    round_number: int,
    players_by_id: dict,
    strategy: str,
    round_intent: str = _INTENT_COMPETITIVE,
) -> list[dict]:
    """
    Assign league pairs to sequential table numbers within a round. Each slot
    carries the additive fields (round_intent, gap_band, roles) derived by
    _build_slot. The inter-academy engine doesn't yet model physical table
    contention or sub-rounds — that arrives in Phase 3 with the multi-wave
    scheduler split.
    """
    slots: list[dict] = []
    for i, (pid_a, pid_b) in enumerate(pairs):
        table = i + 1  # sequential match number within the round
        if pid_a is None and pid_b is None:
            continue
        if pid_a is None or pid_b is None:
            active_id = pid_a if pid_a is not None else pid_b
            slots.append(_build_slot(
                round_number=round_number,
                table_number=table,
                sub_round=None,
                round_intent=round_intent,
                players_by_id=players_by_id,
                player_a_id=active_id,
                player_b_id=None,
                fixture_strategy=strategy,
            ))
            continue
        slots.append(_build_slot(
            round_number=round_number,
            table_number=table,
            sub_round=None,
            round_intent=round_intent,
            players_by_id=players_by_id,
            player_a_id=pid_a,
            player_b_id=pid_b,
            fixture_strategy=strategy,
        ))
    return slots


def _run_circle_round_robin(
    players_by_id: dict,
    pids: list,
    played_pairs: set[tuple],
    strategy: str,
    round_offset: int = 0,
) -> tuple[list[dict], int, int]:
    """
    Full circle-method round-robin on a (possibly BYE-padded) pid list.
    Returns (slots, cross_count, real_count).
    round_offset shifts round numbers so tiers can share a sequential counter.
    """
    total_rounds = len(pids) - 1
    slots: list[dict] = []
    cross_count = 0
    real_count = 0

    for round_idx in range(total_rounds):
        raw_pairs = _circle_pairs_for_ids(pids, round_idx)
        real_pairs = [(a, b) for a, b in raw_pairs if a is not None and b is not None]
        bye_pairs = [(a if a is not None else b, None) for a, b in raw_pairs if a is None or b is None]
        real_pairs = _swap_for_novelty(real_pairs, played_pairs)
        all_pairs = real_pairs + bye_pairs

        round_slots = _assign_tables_league(
            all_pairs, round_offset + round_idx + 1, players_by_id, strategy
        )
        for slot in round_slots:
            if slot["player_b_id"] is not None:
                real_count += 1
                if players_by_id[slot["player_a_id"]]["academy_id"] != players_by_id[slot["player_b_id"]]["academy_id"]:
                    cross_count += 1
        slots.extend(round_slots)

    return slots, cross_count, real_count


def _full_round_robin(players_by_academy: dict, played_pairs: set[tuple]) -> dict:
    """
    Option 1: Every player plays every other player exactly once.
    Circle method with academy interleaving to maximise cross-academy pairings.
    """
    all_players = _interleave_academies(players_by_academy)
    players_by_id = {p["player_id"]: p for p in all_players}
    n = len(all_players)
    if n < 2:
        return {"total_rounds": 0, "cross_academy_pct": 0.0, "slots": []}

    pids: list = [p["player_id"] for p in all_players]
    if n % 2 == 1:
        pids = pids + [None]

    slots, cross_count, real_count = _run_circle_round_robin(
        players_by_id, pids, played_pairs, "FULL_ROUND_ROBIN"
    )
    total_rounds = len(pids) - 1
    cross_pct = round(cross_count / real_count * 100, 1) if real_count > 0 else 0.0
    return {"total_rounds": total_rounds, "cross_academy_pct": cross_pct, "slots": slots}


def _absorb_singleton_tiers(
    tier_by_academy: dict[str, dict[str, list[dict]]],
    tier_order: list[str],
) -> dict[str, dict[str, list[dict]]]:
    """
    Critique #6: a tier containing exactly one player must not be silent-dropped.
    Merge each such player into the adjacent tier whose closest player is the
    smallest gap away. If both neighbors exist, pick the closer one; if only
    one exists, use it. The merged-in player's resulting slots will carry
    gap_band derived from the actual gap (potentially STRETCH or OUT_OF_BAND).

    Returns a new tier→academy→players mapping with singletons absorbed.
    """
    # Snapshot existing tier sizes (players across all academies in that tier).
    sizes: dict[str, int] = {
        t: sum(len(ps) for ps in by_ac.values())
        for t, by_ac in tier_by_academy.items()
    }
    result: dict[str, dict[str, list[dict]]] = {
        t: {aid: list(ps) for aid, ps in by_ac.items()}
        for t, by_ac in tier_by_academy.items()
    }

    def _closest_neighbor_player_rating(target_tier: str) -> float | None:
        if target_tier not in result or not result[target_tier]:
            return None
        ratings = [
            float(p["current_rating"])
            for ps in result[target_tier].values() for p in ps
        ]
        return sum(ratings) / len(ratings) if ratings else None

    for tier in list(result.keys()):
        if sizes.get(tier, 0) != 1:
            continue
        # Locate the singleton player and their academy.
        by_ac = result[tier]
        academy_id, players = next(iter(by_ac.items()))
        singleton = players[0]
        singleton_rating = float(singleton["current_rating"])

        # Find neighbor tiers in the canonical order.
        idx = tier_order.index(tier) if tier in tier_order else -1
        neighbor_candidates: list[str] = []
        if idx > 0:
            neighbor_candidates.append(tier_order[idx - 1])
        if 0 <= idx < len(tier_order) - 1:
            neighbor_candidates.append(tier_order[idx + 1])
        # Only neighbors that actually have players.
        neighbors = [t for t in neighbor_candidates if sizes.get(t, 0) >= 1]
        if not neighbors:
            # No adjacent tier to absorb into — leave the singleton in place;
            # the caller will emit a BYE for it rather than silent-drop.
            continue

        # Choose the neighbor whose mean rating is closest to the singleton.
        def _distance(t: str) -> float:
            mean = _closest_neighbor_player_rating(t) or singleton_rating
            return abs(mean - singleton_rating)

        target = min(neighbors, key=_distance)
        result[target].setdefault(academy_id, []).append(singleton)
        # Remove the singleton's now-empty tier.
        del result[tier]
        sizes[target] = sizes.get(target, 0) + 1
        sizes[tier] = 0

    return result


def _circle_matching_no_same_academy(
    interleaved: list[dict],
    played_pairs: set[tuple],
    strategy: str,
    round_offset: int,
) -> tuple[list[dict], int, int, int]:
    """
    Run the circle method over interleaved players, but enforce the
    no-same-academy contract: every produced pair whose endpoints share an
    academy is replaced by two BYEs (one per affected player) for that round.

    Returns (slots, rounds_emitted, cross_count, real_count). The novelty
    swap is constraint-aware: it only swaps when both replacement pairs would
    remain cross-academy and at least one rematch is avoided.
    """
    players_by_id_local = {p["player_id"]: p for p in interleaved}
    pids: list = [p["player_id"] for p in interleaved]
    if len(pids) < 2:
        # Degenerate group — emit BYE per player so they aren't silent-dropped.
        slots: list[dict] = []
        for i, p in enumerate(interleaved):
            slots.append(_build_slot(
                round_number=round_offset + 1,
                table_number=i + 1,
                sub_round=None,
                round_intent=_INTENT_COMPETITIVE,
                players_by_id=players_by_id_local,
                player_a_id=p["player_id"],
                player_b_id=None,
                fixture_strategy=strategy,
            ))
        return slots, 1 if interleaved else 0, 0, 0
    if len(pids) % 2 == 1:
        pids = pids + [None]

    total_rounds = len(pids) - 1
    slots: list[dict] = []
    cross_count = 0
    real_count = 0

    for round_idx in range(total_rounds):
        raw_pairs = _circle_pairs_for_ids(pids, round_idx)
        cross_pairs: list[tuple] = []
        bye_pairs: list[tuple] = []
        for a, b in raw_pairs:
            if a is None or b is None:
                bye_pairs.append((a if a is not None else b, None))
                continue
            acad_a = players_by_id_local[a]["academy_id"]
            acad_b = players_by_id_local[b]["academy_id"]
            if acad_a == acad_b:
                # Critique #5: TIER_MATCHED with ≥2 academies in a tier must
                # not emit intra-academy pairs. Convert to BYEs.
                bye_pairs.append((a, None))
                bye_pairs.append((b, None))
            else:
                cross_pairs.append((a, b))

        cross_pairs = _swap_for_novelty_constrained(
            cross_pairs, played_pairs, players_by_id_local
        )
        all_pairs = cross_pairs + bye_pairs
        round_slots = _assign_tables_league(
            all_pairs, round_offset + round_idx + 1, players_by_id_local, strategy,
        )
        for slot in round_slots:
            if slot["player_b_id"] is not None:
                real_count += 1
                if players_by_id_local[slot["player_a_id"]]["academy_id"] != \
                        players_by_id_local[slot["player_b_id"]]["academy_id"]:
                    cross_count += 1
        slots.extend(round_slots)

    return slots, total_rounds, cross_count, real_count


def _tier_matched(players_by_academy: dict, played_pairs: set[tuple]) -> dict:
    """
    Option 2 (default): players grouped by rating tier, then cross-academy
    matching within each tier. Same-academy pairs are forbidden when the
    tier contains ≥2 academies (critique §5). Singleton-tier players are
    absorbed into the closest adjacent tier (critique §6) rather than dropped.

    Rounds are numbered sequentially across tiers.
    """
    from app.utils.rating_math import get_tier, _load_config

    cfg = _load_config()

    tier_order = ["NATIONAL_TRACK", "ELITE", "ADVANCED", "INTERMEDIATE", "BEGINNER"]

    # Build per-tier, per-academy groupings.
    tier_by_academy: dict[str, dict[str, list[dict]]] = {}
    for academy_id, players in players_by_academy.items():
        for p in players:
            tier = get_tier(float(p["current_rating"]), cfg)
            tier_by_academy.setdefault(tier, {}).setdefault(academy_id, []).append(p)

    # Absorb singleton tiers into their nearest adjacent tier so the affected
    # players aren't silently dropped.
    tier_by_academy = _absorb_singleton_tiers(tier_by_academy, tier_order)

    all_slots: list[dict] = []
    cross_count = 0
    real_count = 0
    rounds_emitted = 0

    for tier in tier_order:
        by_academy = tier_by_academy.get(tier)
        if not by_academy:
            continue

        interleaved = _interleave_academies(by_academy)
        if not interleaved:
            continue

        tier_slots, tier_rounds, tc, rc = _circle_matching_no_same_academy(
            interleaved, played_pairs, "TIER_MATCHED", rounds_emitted,
        )
        all_slots.extend(tier_slots)
        cross_count += tc
        real_count += rc
        rounds_emitted += tier_rounds

    cross_pct = round(cross_count / real_count * 100, 1) if real_count > 0 else 0.0
    return {"total_rounds": rounds_emitted, "cross_academy_pct": cross_pct, "slots": all_slots}


def _cross_academy_only(players_by_academy: dict, played_pairs: set[tuple]) -> dict:
    """
    Option 3: Circle method, but intra-academy pairs are replaced with BYEs.
    Every scheduled match is guaranteed to be cross-academy.
    Players sit out (BYE) rounds where the circle would have paired them with
    a same-academy teammate.
    """
    all_players = _interleave_academies(players_by_academy)
    players_by_id = {p["player_id"]: p for p in all_players}
    n = len(all_players)
    if n < 2:
        return {"total_rounds": 0, "cross_academy_pct": 0.0, "slots": []}

    pids: list = [p["player_id"] for p in all_players]
    if n % 2 == 1:
        pids = pids + [None]

    total_rounds = len(pids) - 1
    slots: list[dict] = []
    cross_count = 0
    real_count = 0

    for round_idx in range(total_rounds):
        raw_pairs = _circle_pairs_for_ids(pids, round_idx)
        real_pairs = [(a, b) for a, b in raw_pairs if a is not None and b is not None]
        bye_pairs = [(a if a is not None else b, None) for a, b in raw_pairs if a is None or b is None]

        cross_pairs = []
        for a, b in real_pairs:
            if players_by_id[a]["academy_id"] != players_by_id[b]["academy_id"]:
                cross_pairs.append((a, b))
            else:
                # Same-academy pair → both players get a BYE this round
                bye_pairs.append((a, None))
                bye_pairs.append((b, None))

        cross_pairs = _swap_for_novelty_constrained(
            cross_pairs, played_pairs, players_by_id
        )
        all_pairs = cross_pairs + bye_pairs

        round_slots = _assign_tables_league(
            all_pairs, round_idx + 1, players_by_id, "CROSS_ACADEMY_ONLY"
        )
        for slot in round_slots:
            if slot["player_b_id"] is not None:
                real_count += 1
                cross_count += 1  # all real matches are cross-academy by construction
        slots.extend(round_slots)

    cross_pct = 100.0 if real_count > 0 else 0.0
    return {"total_rounds": total_rounds, "cross_academy_pct": cross_pct, "slots": slots}


def _team_format(players_by_academy: dict, _played_pairs: set[tuple]) -> dict:
    """
    Option 4: Structured as Academy A vs Academy B, A vs C, B vs C …
    Within each matchup, players are paired positionally by intra-academy rating rank
    (#1 vs #1, #2 vs #2, …). Unmatched positions (different academy sizes) get BYEs.
    Each academy-pair matchup occupies one round number.
    """
    sorted_academies: dict[str, list[dict]] = {
        aid: sorted(players, key=lambda p: float(p["current_rating"]), reverse=True)
        for aid, players in players_by_academy.items()
    }
    players_by_id = {
        p["player_id"]: p
        for players in sorted_academies.values()
        for p in players
    }
    academy_ids = list(sorted_academies.keys())

    slots: list[dict] = []
    cross_count = 0
    real_count = 0
    round_number = 1

    for i in range(len(academy_ids)):
        for j in range(i + 1, len(academy_ids)):
            aid_a = academy_ids[i]
            aid_b = academy_ids[j]
            team_a = sorted_academies[aid_a]
            team_b = sorted_academies[aid_b]
            max_pos = max(len(team_a), len(team_b))

            round_slots: list[dict] = []
            for pos in range(max_pos):
                p_a = team_a[pos] if pos < len(team_a) else None
                p_b = team_b[pos] if pos < len(team_b) else None

                if p_a is None and p_b is None:
                    continue
                if p_a is None or p_b is None:
                    present = p_a if p_a is not None else p_b
                    round_slots.append(_build_slot(
                        round_number=round_number,
                        table_number=pos + 1,
                        sub_round=None,
                        round_intent=_INTENT_COMPETITIVE,
                        players_by_id=players_by_id,
                        player_a_id=present["player_id"],
                        player_b_id=None,
                        fixture_strategy="TEAM_FORMAT",
                    ))
                    continue
                real_count += 1
                cross_count += 1
                round_slots.append(_build_slot(
                    round_number=round_number,
                    table_number=pos + 1,
                    sub_round=None,
                    round_intent=_INTENT_COMPETITIVE,
                    players_by_id=players_by_id,
                    player_a_id=p_a["player_id"],
                    player_b_id=p_b["player_id"],
                    fixture_strategy="TEAM_FORMAT",
                ))

            slots.extend(round_slots)
            round_number += 1

    total_rounds = round_number - 1
    cross_pct = round(cross_count / real_count * 100, 1) if real_count > 0 else 0.0
    return {"total_rounds": total_rounds, "cross_academy_pct": cross_pct, "slots": slots}


FIXTURE_STRATEGIES = {"FULL_ROUND_ROBIN", "TIER_MATCHED", "CROSS_ACADEMY_ONLY", "TEAM_FORMAT"}


def generate_league_fixtures(
    players_by_academy: dict[str, list[dict]],
    played_pairs: set[tuple],
    strategy: str = "TIER_MATCHED",
) -> dict:
    """
    Generate inter-academy league fixtures using the selected strategy.

    Strategy options:
      TIER_MATCHED       (default) — cross-academy round-robin within each rating tier.
                                     Maximises COMPETITIVE matches.
      CROSS_ACADEMY_ONLY           — circle method, intra-academy pairs replaced with BYEs.
                                     Every match is cross-academy.
      TEAM_FORMAT                  — positional matchups per academy pair (#1v#1, #2v#2 …).
                                     Closest to real inter-club team competition.
      FULL_ROUND_ROBIN             — every player vs every other player (original behaviour).
                                     Produces many STRETCH matches when academies differ in level.

    players_by_academy: {academy_id: [player_dict, ...]} each sorted by rating desc.
      Each player_dict must have: player_id, name, current_rating, academy_id, academy_name.
    played_pairs: canonical (a, b) tuples from the immediately preceding league event.

    Returns: {"total_rounds": int, "cross_academy_pct": float, "slots": list[dict]}
    """
    dispatch = {
        "FULL_ROUND_ROBIN": _full_round_robin,
        "TIER_MATCHED": _tier_matched,
        "CROSS_ACADEMY_ONLY": _cross_academy_only,
        "TEAM_FORMAT": _team_format,
    }
    fn = dispatch.get(strategy, _tier_matched)
    return fn(players_by_academy, played_pairs)
