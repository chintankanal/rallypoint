"""
Rating engine: atomic batch Elo application and match rollback.

apply_ratings_batch(conn, match_ids) — called inside a get_connection() context.
rollback_match(conn, match_id)       — called inside a get_connection() context.

The caller owns the transaction; this module never commits or rolls back directly.
"""
import json
import uuid
from datetime import date, datetime, timezone
from threading import Lock

from cachetools import TTLCache

from app.utils.rating_math import (
    get_actual_score,
    get_age_bonus,
    get_asi_adjusted_rating,
    get_cr,
    get_effective_event_type,
    get_expected_score,
    get_k_base,
    get_k_eff,
    get_k_shared,
    get_match_weight,
    get_academy_weight,
    get_tier,
)

# ── Config cache: one entry, 60-second TTL ────────────────────────────────────
_config_cache: TTLCache = TTLCache(maxsize=1, ttl=60)
_cache_lock = Lock()


def _load_config(cur) -> dict[str, float]:
    """Return system_configuration as {key: float}, with 60s in-process cache."""
    with _cache_lock:
        cached = _config_cache.get("cfg")
        if cached is not None:
            return cached
        cur.execute("SELECT key, value FROM system_configuration")
        rows = cur.fetchall()
        cfg = {r["key"]: float(r["value"]) for r in rows}
        _config_cache["cfg"] = cfg
        return cfg


def invalidate_config_cache() -> None:
    """Call after PATCH /config to force next read to hit the DB."""
    with _cache_lock:
        _config_cache.clear()


# ── ASI helpers ───────────────────────────────────────────────────────────────

def _load_asi_for_academies(cur, academy_ids: set[str], global_avg: float) -> dict[str, float]:
    """Return {academy_id: asi_value}. Falls back to global_avg when DEFAULTED/missing."""
    if not academy_ids:
        return {}
    placeholders = ",".join(["%s"] * len(academy_ids))
    cur.execute(
        f"""
        SELECT DISTINCT ON (academy_id)
            academy_id, asi_value, calculation_basis
        FROM academy_asi_history
        WHERE academy_id IN ({placeholders})
        ORDER BY academy_id, calculated_at DESC
        """,
        list(academy_ids),
    )
    result: dict[str, float] = {}
    for row in cur.fetchall():
        if row["calculation_basis"] == "DEFAULTED" or row["asi_value"] is None:
            result[row["academy_id"]] = global_avg
        else:
            result[row["academy_id"]] = float(row["asi_value"])
    # Academies with no history at all → global_avg
    for aid in academy_ids:
        result.setdefault(aid, global_avg)
    return result


def _recalculate_asi(cur, academy_ids: set[str], global_avg: float) -> None:
    """
    Recompute ASI for each affected academy and insert a new AcademyASIHistory row.
    Qualifying: ACTIVE, ≥15 rated matches, last_match_date within 8 weeks.
    COMPUTED if ≥5 qualifying players, DEFAULTED otherwise.
    """
    eight_weeks_ago = "NOW() - INTERVAL '56 days'"
    for academy_id in academy_ids:
        cur.execute(
            f"""
            SELECT AVG(current_rating) AS avg_rating, COUNT(*) AS cnt
            FROM player
            WHERE primary_academy_id = %s
              AND status = 'ACTIVE'
              AND rated_matches_completed >= 15
              AND last_match_date >= {eight_weeks_ago}
            """,
            (academy_id,),
        )
        row = cur.fetchone()
        count = int(row["cnt"]) if row["cnt"] else 0
        avg = float(row["avg_rating"]) if row["avg_rating"] else global_avg

        if count >= 5:
            asi_value = avg
            basis = "COMPUTED"
        else:
            asi_value = None
            basis = "DEFAULTED"

        cur.execute(
            """
            INSERT INTO academy_asi_history
                (history_id, academy_id, asi_value, qualifying_player_count,
                 calculation_basis, global_average_at_calculation)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), academy_id, asi_value, count, basis, global_avg),
        )


def _update_global_average(cur) -> float:
    """Recompute global average rating of all ACTIVE players and persist it."""
    cur.execute(
        "SELECT AVG(current_rating) AS avg FROM player WHERE status = 'ACTIVE'"
    )
    row = cur.fetchone()
    new_avg = float(row["avg"]) if row["avg"] else 1000.0
    cur.execute(
        "UPDATE system_configuration SET value = %s, updated_at = NOW() "
        "WHERE key = 'global_average_rating'",
        (str(new_avg),),
    )
    return new_avg


# ── Core batch processor ──────────────────────────────────────────────────────

def apply_ratings_batch(conn, match_ids: list[str]) -> list[dict]:
    """
    Apply Elo ratings for a list of confirmed, eligible, unrated matches.
    Returns a list of {match_id, tier_changed, player_id, tier_before, tier_after}
    for each tier-change event (caller fires webhooks after commit).

    Must be called inside a get_connection() context (caller owns the transaction).
    """
    if not match_ids:
        return []

    with conn.cursor() as cur:
        # 1. Load matches in chronological order
        placeholders = ",".join(["%s"] * len(match_ids))
        cur.execute(
            f"""
            SELECT m.match_id, m.player_a_id, m.player_b_id,
                   m.player_a_academy_id, m.player_b_academy_id,
                   m.winner_id, m.match_format,
                   m.sets_won_a, m.sets_won_b,
                   m.is_retirement, m.diminishing_signal_applied,
                   m.event_id, m.match_date, m.match_timestamp,
                   e.event_type, e.scheduling_mode,
                   pa.date_of_birth AS dob_a,
                   pb.date_of_birth AS dob_b
            FROM match m
            JOIN event e ON e.event_id = m.event_id
            JOIN player pa ON pa.player_id = m.player_a_id
            JOIN player pb ON pb.player_id = m.player_b_id
            WHERE m.match_id IN ({placeholders})
              AND m.rating_eligible = TRUE
              AND m.ratings_applied_at IS NULL
            ORDER BY m.match_timestamp ASC
            """,
            match_ids,
        )
        matches = [dict(r) for r in cur.fetchall()]
        if not matches:
            return []

        # 2. Lock all player rows for this transaction
        player_ids = set()
        for m in matches:
            player_ids.add(m["player_a_id"])
            player_ids.add(m["player_b_id"])

        ph = ",".join(["%s"] * len(player_ids))
        cur.execute(
            f"""
            SELECT player_id, current_rating, rated_matches_completed,
                   virtual_matches, last_match_date, primary_academy_id
            FROM player WHERE player_id IN ({ph})
            FOR UPDATE
            """,
            list(player_ids),
        )
        player_map: dict[str, dict] = {r["player_id"]: dict(r) for r in cur.fetchall()}

        # 3. Load config + ASI
        cfg = _load_config(cur)
        global_avg = cfg.get("global_average_rating", 1000.0)

        academy_ids = {p["primary_academy_id"] for p in player_map.values()}
        for m in matches:
            academy_ids.add(m["player_a_academy_id"])
            academy_ids.add(m["player_b_academy_id"])
        asi_map = _load_asi_for_academies(cur, academy_ids, global_avg)

        # Track tier changes for post-commit webhooks
        tier_changes: list[dict] = []
        now_utc = datetime.now(timezone.utc)

        # 4. Process each match sequentially
        for m in matches:
            pid_a = m["player_a_id"]
            pid_b = m["player_b_id"]
            p_a = player_map[pid_a]
            p_b = player_map[pid_b]

            eff_type = get_effective_event_type(
                m["event_type"], m["diminishing_signal_applied"]
            )

            # ASI adjustment uses the academy snapshot at match time
            asi_a = asi_map.get(m["player_a_academy_id"], global_avg)
            asi_b = asi_map.get(m["player_b_academy_id"], global_avg)

            r_a = float(p_a["current_rating"])
            r_b = float(p_b["current_rating"])
            r_adj_a = get_asi_adjusted_rating(r_a, global_avg, asi_a)
            r_adj_b = get_asi_adjusted_rating(r_b, global_avg, asi_b)

            exp_a = get_expected_score(r_adj_a, r_adj_b)

            same_academy = m["player_a_academy_id"] == m["player_b_academy_id"]
            w_match = get_match_weight(eff_type)
            w_academy = get_academy_weight(same_academy)

            n_a = p_a["rated_matches_completed"] + p_a["virtual_matches"]
            n_b = p_b["rated_matches_completed"] + p_b["virtual_matches"]
            cr_a = get_cr(n_a)
            cr_b = get_cr(n_b)

            k_base_a = get_k_base(p_a["rated_matches_completed"])
            k_base_b = get_k_base(p_b["rated_matches_completed"])
            k_eff_a = get_k_eff(k_base_a, w_match, w_academy, cr_a)
            k_eff_b = get_k_eff(k_base_b, w_match, w_academy, cr_b)
            k_shared = get_k_shared(k_eff_a, k_eff_b)

            # Identify winner and loser from stored canonical data
            winner_id = m["winner_id"]
            loser_id = pid_b if winner_id == pid_a else pid_a

            if winner_id == pid_a:
                sets_winner, sets_loser = m["sets_won_a"], m["sets_won_b"]
                exp_winner = exp_a
                dob_winner = m["dob_a"]
                dob_loser = m["dob_b"]
            else:
                sets_winner, sets_loser = m["sets_won_b"], m["sets_won_a"]
                exp_winner = 1 - exp_a
                dob_winner = m["dob_b"]
                dob_loser = m["dob_a"]

            # Retirement: if winner didn't reach required sets, use actual credited score
            act_winner, act_loser = get_actual_score(
                sets_winner, sets_loser, m["match_format"]
            )

            delta = k_shared * (act_winner - exp_winner)

            # Upset: lower R_adj player wins
            r_adj_winner = r_adj_a if winner_id == pid_a else r_adj_b
            r_adj_loser = r_adj_b if winner_id == pid_a else r_adj_a
            is_upset = r_adj_winner < r_adj_loser
            age_bonus = get_age_bonus(dob_winner, dob_loser, is_upset)

            r_winner = float(player_map[winner_id]["current_rating"])
            r_loser = float(player_map[loser_id]["current_rating"])

            tier_before_winner = get_tier(r_winner)
            tier_before_loser = get_tier(r_loser)
            cr_before_winner = get_cr(
                player_map[winner_id]["rated_matches_completed"]
                + player_map[winner_id]["virtual_matches"]
            )
            cr_before_loser = get_cr(
                player_map[loser_id]["rated_matches_completed"]
                + player_map[loser_id]["virtual_matches"]
            )

            new_r_winner = r_winner + delta + age_bonus
            new_r_loser = r_loser - delta - age_bonus

            tier_after_winner = get_tier(new_r_winner)
            tier_after_loser = get_tier(new_r_loser)

            k_base_winner = (
                k_base_a if winner_id == pid_a else k_base_b
            )
            k_base_loser = (
                k_base_b if winner_id == pid_a else k_base_a
            )
            k_eff_winner = k_eff_a if winner_id == pid_a else k_eff_b
            k_eff_loser = k_eff_b if winner_id == pid_a else k_eff_a

            delta_breakdown = {
                "k_shared": round(k_shared, 4),
                "actual_score_winner": act_winner,
                "expected_score_winner": round(exp_winner, 4),
                "w_match": w_match,
                "w_academy": w_academy,
                "same_academy": same_academy,
                "effective_event_type": eff_type,
                "diminishing_signal": m["diminishing_signal_applied"],
                "is_upset": is_upset,
                "age_bonus": round(age_bonus, 4),
                "asi_a": round(asi_a, 4),
                "asi_b": round(asi_b, 4),
                "r_adj_winner": round(r_adj_winner, 4),
                "r_adj_loser": round(r_adj_loser, 4),
            }

            # Write RatingHistory for winner
            winner_hist_id = str(uuid.uuid4())
            loser_hist_id = str(uuid.uuid4())
            cr_after_winner = get_cr(
                player_map[winner_id]["rated_matches_completed"] + 1
                + player_map[winner_id]["virtual_matches"]
            )
            cr_after_loser = get_cr(
                player_map[loser_id]["rated_matches_completed"] + 1
                + player_map[loser_id]["virtual_matches"]
            )

            for hist_id, pid, r_before, r_after, tier_before, tier_after, \
                    cr_before, cr_after, k_b, k_e, exp_score, act_score in [
                (winner_hist_id, winner_id, r_winner, new_r_winner,
                 tier_before_winner, tier_after_winner,
                 cr_before_winner, cr_after_winner,
                 k_base_winner, k_eff_winner, exp_winner, act_winner),
                (loser_hist_id, loser_id, r_loser, new_r_loser,
                 tier_before_loser, tier_after_loser,
                 cr_before_loser, cr_after_loser,
                 k_base_loser, k_eff_loser, 1 - exp_winner, act_loser),
            ]:
                actual_delta = r_after - r_before
                cur.execute(
                    """
                    INSERT INTO rating_history (
                        history_id, player_id, match_id,
                        rating_before, rating_after, delta,
                        delta_breakdown, tier_before, tier_after,
                        cr_before, cr_after, k_base, k_eff, k_shared,
                        expected_score, actual_score, age_bonus
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    """,
                    (
                        hist_id, pid, m["match_id"],
                        round(r_before, 2), round(r_after, 2), round(actual_delta, 2),
                        json.dumps(delta_breakdown), tier_before, tier_after,
                        round(cr_before, 4), round(cr_after, 4),
                        round(k_b, 2), round(k_e, 2), round(k_shared, 2),
                        round(exp_score, 4), act_score, round(age_bonus, 2),
                    ),
                )

            # Update player rows and in-memory map
            match_date = m["match_date"]
            if isinstance(match_date, str):
                match_date = date.fromisoformat(match_date)

            for pid, new_r in [(winner_id, new_r_winner), (loser_id, new_r_loser)]:
                cur.execute(
                    """
                    UPDATE player
                    SET current_rating = %s,
                        rated_matches_completed = rated_matches_completed + 1,
                        last_match_date = GREATEST(COALESCE(last_match_date, %s), %s)
                    WHERE player_id = %s
                    """,
                    (round(new_r, 2), match_date, match_date, pid),
                )
                player_map[pid]["current_rating"] = new_r
                player_map[pid]["rated_matches_completed"] += 1
                if (
                    player_map[pid]["last_match_date"] is None
                    or match_date > player_map[pid]["last_match_date"]
                ):
                    player_map[pid]["last_match_date"] = match_date

            # Mark match as rated
            cur.execute(
                "UPDATE match SET ratings_applied_at = %s WHERE match_id = %s",
                (now_utc, m["match_id"]),
            )

            # Collect tier changes for post-commit webhooks
            if tier_before_winner != tier_after_winner:
                tier_changes.append({
                    "match_id": m["match_id"], "player_id": winner_id,
                    "tier_before": tier_before_winner, "tier_after": tier_after_winner,
                })
            if tier_before_loser != tier_after_loser:
                tier_changes.append({
                    "match_id": m["match_id"], "player_id": loser_id,
                    "tier_before": tier_before_loser, "tier_after": tier_after_loser,
                })

        # 5. Recalculate ASI for all affected academies
        affected_academies = {p["primary_academy_id"] for p in player_map.values()}
        new_global_avg = _update_global_average(cur)
        _recalculate_asi(cur, affected_academies, new_global_avg)

    return tier_changes


# ── Rollback ──────────────────────────────────────────────────────────────────

def rollback_match(conn, match_id: str) -> None:
    """
    Reverse previously applied ratings for a single match.
    Writes negated RatingHistory rows (is_rollback=TRUE) and updates player ratings.
    Does NOT recalculate subsequent matches.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rh.history_id, rh.player_id, rh.delta, rh.rating_before, rh.rating_after
            FROM rating_history rh
            WHERE rh.match_id = %s AND rh.is_rollback = FALSE
            ORDER BY rh.created_at ASC
            """,
            (match_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return  # Nothing to roll back

        for row in rows:
            rollback_id = str(uuid.uuid4())
            negated_delta = -float(row["delta"])
            new_rating = float(row["rating_before"])  # restore to pre-match rating

            cur.execute(
                """
                INSERT INTO rating_history (
                    history_id, player_id, match_id,
                    rating_before, rating_after, delta,
                    delta_breakdown, tier_before, tier_after,
                    cr_before, cr_after, k_base, k_eff, k_shared,
                    expected_score, actual_score, age_bonus,
                    is_rollback, rollback_of_history_id
                )
                SELECT
                    %s, player_id, match_id,
                    rating_after, %s, %s,
                    delta_breakdown, tier_after, tier_before,
                    cr_after, cr_before, k_base, k_eff, k_shared,
                    expected_score, actual_score, age_bonus,
                    TRUE, history_id
                FROM rating_history WHERE history_id = %s
                """,
                (rollback_id, new_rating, negated_delta, row["history_id"]),
            )

            cur.execute(
                """
                UPDATE player
                SET current_rating = %s,
                    rated_matches_completed = GREATEST(0, rated_matches_completed - 1)
                WHERE player_id = %s
                """,
                (round(new_rating, 2), row["player_id"]),
            )

        # Clear ratings_applied_at so match can be re-rated if needed
        cur.execute(
            "UPDATE match SET ratings_applied_at = NULL WHERE match_id = %s",
            (match_id,),
        )
