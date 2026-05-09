"""
Fixture engine: pure Python, zero DB access, fully unit-testable.

All functions accept and return plain dicts/lists of player dicts:
  player = {"player_id": str, "name": str, "current_rating": float}

Returned slot dicts:
  {
    "round_number": int,
    "sub_round": str | None,   # "A" or "B" when two sub-rounds needed
    "table_number": int,
    "match_category": str,     # COMPETITIVE | STRETCH | ANCHOR (COMPETITIVE for BYE)
    "player_a_id": str,        # canonical: player_a_id < player_b_id
    "player_b_id": str | None, # None = BYE slot
    "expected_rating_gap": float,
  }
"""
import math
from typing import Optional

# Match duration in minutes (not including 5-min changeover)
_MATCH_DURATION = {"BEST_OF_3": 20, "BEST_OF_5": 30, "BEST_OF_7": 40}
_CHANGEOVER = 5

# Gap thresholds for match category classification
_COMPETITIVE_MAX = 100   # gap ≤ 100 → COMPETITIVE
_STRETCH_MAX = 250       # gap 100 < x ≤ 250 → STRETCH/ANCHOR


# ── Phase detection ───────────────────────────────────────────────────────────

def detect_phase(players: list[dict]) -> str:
    """
    DISCOVERY  : spread < 100
    TRANSITION : 100 ≤ spread < 250
    STANDARD   : spread ≥ 250
    """
    if len(players) < 2:
        return "DISCOVERY"
    ratings = [float(p["current_rating"]) for p in players]
    spread = max(ratings) - min(ratings)
    if spread < 100:
        return "DISCOVERY"
    if spread < 250:
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


def _category(gap: float) -> str:
    if gap <= _COMPETITIVE_MAX:
        return "COMPETITIVE"
    return "STRETCH"  # any gap > 100 is a developmental match


# ── Table assignment ──────────────────────────────────────────────────────────

def _assign_tables(
    pairs: list[tuple[Optional[str], Optional[str]]],
    num_tables: int,
    round_number: int,
    match_category: str,
    players_by_id: dict,
) -> list[dict]:
    """
    Assign pairs to tables. If more pairs than tables, split into sub-rounds A/B.
    Returns list of slot dicts.
    """
    slots = []
    if not pairs:
        return slots

    needs_subrounds = len(pairs) > num_tables

    for i, (pid_a, pid_b) in enumerate(pairs):
        if pid_a is None or pid_b is None:
            # BYE slot — player_b_id is None
            active_id = pid_a if pid_a is not None else pid_b
            sub = ("A" if i < num_tables else "B") if needs_subrounds else None
            table = (i % num_tables) + 1
            slots.append({
                "round_number": round_number,
                "sub_round": sub,
                "table_number": table,
                "match_category": "COMPETITIVE",
                "player_a_id": active_id,
                "player_b_id": None,
                "expected_rating_gap": 0.0,
            })
            continue

        canon_a, canon_b = _canonical(pid_a, pid_b)
        gap = _gap(players_by_id, canon_a, canon_b)
        sub = ("A" if i < num_tables else "B") if needs_subrounds else None
        table = (i % num_tables) + 1

        # Bug 2 fix: derive label from actual gap for competitive rounds so
        # cross-tier leftover pairs (gap 100-250) are correctly labeled STRETCH.
        actual_category = _category(gap) if match_category == "COMPETITIVE" else match_category
        slots.append({
            "round_number": round_number,
            "sub_round": sub,
            "table_number": table,
            "match_category": actual_category,
            "player_a_id": canon_a,
            "player_b_id": canon_b,
            "expected_rating_gap": round(gap, 2),
        })
    return slots


# ── Phase A: Discovery (circle-method round-robin) ────────────────────────────

def _circle_round(players: list[dict], round_idx: int) -> list[tuple]:
    """
    Return pairs for round_idx (0-indexed) using the standard circle method.
    If odd number of players, a BYE sentinel (None) is added.
    """
    ps = list(players)
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
    All matches are COMPETITIVE.
    """
    players_by_id = {p["player_id"]: p for p in players}
    n = len(players)
    total_rounds = (n if n % 2 == 1 else n - 1)  # full round-robin cycle

    slots: list[dict] = []
    for step in range(matches_per_player):
        round_idx = (round_offset + step) % total_rounds
        pairs = _circle_round(players, round_idx)
        round_number = round_offset + step + 1
        slots.extend(
            _assign_tables(pairs, num_tables, round_number, "COMPETITIVE", players_by_id)
        )
    return slots


# ── Phase B: Transition (median split) ───────────────────────────────────────

def generate_transition_fixtures(
    players: list[dict],
    matches_per_player: int,
    num_tables: int,
) -> list[dict]:
    """
    Sort by rating desc. Split at median.
    Competitive rounds pair within each half; stretch round crosses halves.
    """
    sorted_players = sorted(players, key=lambda p: float(p["current_rating"]), reverse=True)
    players_by_id = {p["player_id"]: p for p in players}
    n = len(sorted_players)
    mid = n // 2
    upper = sorted_players[:mid]      # higher rated
    lower = sorted_players[mid:]      # lower rated (may have extra player if odd)

    slots: list[dict] = []
    round_number = 1
    competitive_done = 0

    def within_half_pairs(half: list[dict], shift: int) -> list[tuple]:
        """Adjacent pairing within a half, with optional shift for the second competitive round."""
        pids = [p["player_id"] for p in half]
        pairs = []
        start = shift % max(1, len(pids) - 1)
        visited = set()
        for i in range(len(pids) - 1):
            idx = (i + start) % (len(pids) - 1)
            a, b = pids[idx], pids[(idx + 1) % len(pids)]
            key = _canonical(a, b)
            if key not in visited:
                visited.add(key)
                pairs.append((a, b))
        # BYE if odd
        if len(pids) % 2 == 1:
            paired = {pid for pair in pairs for pid in pair}
            for pid in pids:
                if pid not in paired:
                    pairs.append((pid, None))
                    break
        return pairs

    def cross_pairs() -> list[tuple]:
        """Top of lower half vs bottom of upper half."""
        pairs = []
        # lower[0] is highest rated in lower half; upper[-1] is lowest in upper half
        for i in range(min(len(lower), len(upper))):
            pairs.append((lower[i]["player_id"], upper[-(i + 1)]["player_id"]))
        return pairs

    for step in range(matches_per_player):
        is_stretch_round = (step == 1)  # round 2 (index 1) is stretch

        if is_stretch_round:
            pairs = cross_pairs()
            slots.extend(_assign_tables(pairs, num_tables, round_number, "STRETCH", players_by_id))
        else:
            shift = competitive_done
            pairs_upper = within_half_pairs(upper, shift)
            pairs_lower = within_half_pairs(lower, shift)
            all_pairs = pairs_upper + pairs_lower
            slots.extend(
                _assign_tables(all_pairs, num_tables, round_number, "COMPETITIVE", players_by_id)
            )
            competitive_done += 1

        round_number += 1

    return slots


# ── Phase C: Standard (full competitive + folded stretch) ─────────────────────

def generate_standard_fixtures(
    players: list[dict],
    recent_match_pairs: set[tuple],
    matches_per_player: int,
    num_tables: int,
) -> list[dict]:
    """
    Standard algorithm:
    - Competitive rounds: adjacent pairing within tier
    - Stretch round (round 2): folded pairing k vs k + floor(N/4), gap filter 100–250
    - BYE for odd player count (rotating)
    - recent_match_pairs: canonical (a,b) pairs to exclude from stretch round
    """
    from app.utils.rating_math import get_tier

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
            t = get_tier(float(players_by_id[pid]["current_rating"]))
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

        # Pair leftover border players from adjacent tiers with each other.
        # Any final odd leftover gets a BYE.
        for i in range(0, len(leftovers) - 1, 2):
            pairs.append((leftovers[i], leftovers[i + 1]))
        if len(leftovers) % 2 == 1:
            pairs.append((leftovers[-1], None))  # BYE

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

        # Priority pass: give last BYE player first pick of stretch partners
        if priority_pid is not None and priority_pid in pids:
            k = pids.index(priority_pid)
            for offset in range(fold, n - k):
                pid_b = pids[k + offset]
                if pid_b in used:
                    continue
                gap = _gap(players_by_id, priority_pid, pid_b)
                canon = _canonical(priority_pid, pid_b)
                if canon in all_exclude:
                    continue
                if _COMPETITIVE_MAX <= gap <= _STRETCH_MAX:
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
                if pid_b in used:
                    continue
                gap = _gap(players_by_id, pid_a, pid_b)
                canon = _canonical(pid_a, pid_b)
                if canon in all_exclude:
                    continue
                if gap < _COMPETITIVE_MAX:
                    continue
                if gap <= _STRETCH_MAX:
                    pairs.append(canon)
                    used.add(pid_a)
                    used.add(pid_b)
                    break
                # gap > 250 → keep searching closer

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
    round_number = 1
    competitive_shift = 0
    last_bye_pid: str | None = None
    session_pairs: set[tuple] = set()  # Bug 4: track pairs already played this session

    for step in range(matches_per_player):
        is_stretch = (step == 2) if has_odd_tier else (step % 2 == 1)

        if is_stretch:
            pairs = stretch_pairs(priority_pid=last_bye_pid, extra_exclude=session_pairs)

            # Bug 3: general fallback — any player still unpaired after the strict
            # 100–250 sweep gets paired with their nearest available partner.
            paired_ids = {pid for pair in pairs for pid in pair if pid is not None}
            unpaired = [pid for pid in pids if pid not in paired_ids]
            for i in range(0, len(unpaired) - 1, 2):
                pairs.append(_canonical(unpaired[i], unpaired[i + 1]))
            if len(unpaired) % 2 == 1:
                pairs.append((unpaired[-1], None))  # BYE

            slots.extend(
                _assign_tables(pairs, num_tables, round_number, "STRETCH", players_by_id)
            )
        else:
            pairs = competitive_pairs(competitive_shift, bye_rotation=competitive_shift)
            bye_list = [p[0] for p in pairs if p[1] is None]
            last_bye_pid = bye_list[0] if bye_list else None
            slots.extend(
                _assign_tables(pairs, num_tables, round_number, "COMPETITIVE", players_by_id)
            )
            competitive_shift += 1

        # Bug 4: record pairs played this round for stretch dedup
        for pair in pairs:
            if pair[0] is not None and pair[1] is not None:
                session_pairs.add(_canonical(pair[0], pair[1]))

        round_number += 1

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
    phase = detect_phase(players)
    spread = rating_spread(players)
    capacity = calculate_session_capacity(
        session_minutes, num_tables, match_format, len(players)
    )
    num_rounds = capacity["num_rounds"]  # Bug 1 fix: use round count, not per-player count
    mpp = capacity["matches_per_player"]

    if num_rounds == 0:
        return {"phase": phase, "spread": spread, "matches_per_player": 0, "slots": []}

    if phase == "DISCOVERY":
        slots = generate_discovery_fixtures(players, round_offset, num_rounds, num_tables)
    elif phase == "TRANSITION":
        slots = generate_transition_fixtures(players, num_rounds, num_tables)
    else:
        slots = generate_standard_fixtures(players, recent_match_pairs, num_rounds, num_tables)

    return {
        "phase": phase,
        "spread": spread,
        "matches_per_player": mpp,
        "slots": slots,
    }
