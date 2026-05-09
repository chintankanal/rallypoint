import uuid
from datetime import date

from dateutil.relativedelta import relativedelta

from app.database import get_connection
from app.utils.rating_math import get_age_as_of_jan1, get_age_group, get_cr, get_tier

_SEEDING_DEFAULTS: dict[str, tuple[float, int]] = {
    "UNSEEDED": (1000.0, 0),
    "DISTRICT": (1200.0, 10),
    "STATE":    (1400.0, 20),
    "NATIONAL": (1500.0, 30),
}

_PLAYER_SELECT = """
    SELECT p.player_id, p.name, p.date_of_birth, p.gender, p.nationality,
           p.current_rating, p.rated_matches_completed,
           p.virtual_matches, p.seeding_level, p.last_match_date, p.status,
           p.guardian_name, p.guardian_phone, p.contact_email, p.created_at,
           json_build_object(
               'academy_id', a.academy_id, 'name', a.name,
               'city', a.city, 'state', a.state
           ) AS primary_academy
    FROM player p
    JOIN academy a ON a.academy_id = p.primary_academy_id
    WHERE p.player_id = %s
"""


def create_player(body, created_by_id: str) -> dict:
    starting_rating, default_virtual = _SEEDING_DEFAULTS.get(
        body.seeding_level.value, (1000.0, 0)
    )
    virtual_matches = body.virtual_matches if body.virtual_matches is not None else default_virtual

    player_id = str(uuid.uuid4())
    history_id = str(uuid.uuid4())

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO player (
                    player_id, name, date_of_birth, gender, nationality,
                    primary_academy_id, seeding_level, seeding_reference,
                    virtual_matches, current_rating,
                    guardian_name, guardian_phone, contact_email,
                    created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    player_id,
                    body.name,
                    body.date_of_birth,
                    body.gender.value if body.gender else None,
                    body.nationality,
                    body.primary_academy_id,
                    body.seeding_level.value,
                    body.seeding_reference,
                    virtual_matches,
                    starting_rating,
                    body.guardian_name,
                    body.guardian_phone,
                    body.contact_email,
                    created_by_id,
                    created_by_id,
                ),
            )
            # Seed initial status history row for audit trail
            cur.execute(
                """
                INSERT INTO player_status_history
                    (history_id, player_id, from_status, to_status, reason, changed_by)
                VALUES (%s, %s, NULL, 'ACTIVE', 'Initial registration', %s)
                """,
                (history_id, player_id, created_by_id),
            )
            cur.execute(_PLAYER_SELECT, (player_id,))
            return cur.fetchone()


def get_player(player_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_PLAYER_SELECT, (player_id,))
            return cur.fetchone()


def search_players(q: str, academy_id: str | None, limit: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            params: list = [f"%{q}%"]
            academy_clause = ""
            if academy_id:
                academy_clause = "AND p.primary_academy_id = %s"
                params.append(academy_id)
            params.append(limit)
            cur.execute(
                f"""
                SELECT p.player_id::text, p.name, p.current_rating::float,
                       a.name AS academy_name
                FROM player p
                LEFT JOIN academy a ON a.academy_id = p.primary_academy_id
                WHERE p.status = 'ACTIVE' AND p.name ILIKE %s
                  {academy_clause}
                ORDER BY p.name
                LIMIT %s
                """,
                params,
            )
            return [dict(r) for r in cur.fetchall()]


def get_computed_stats(player_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, current_rating, rated_matches_completed, virtual_matches, "
                "last_match_date, seeding_level, date_of_birth "
                "FROM player WHERE player_id = %s",
                (player_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    today = date.today()
    total_matches = row["rated_matches_completed"] + row["virtual_matches"]
    age_jan1 = get_age_as_of_jan1(row["date_of_birth"])
    cr = get_cr(total_matches)
    is_provisional = row["seeding_level"] == "UNSEEDED" and total_matches < 15
    provisional_remaining = max(0, 15 - total_matches) if is_provisional else 0

    weeks_inactive: float | None = None
    if row["last_match_date"]:
        weeks_inactive = round((today - row["last_match_date"]).days / 7, 2)

    return {
        "player_id": player_id,
        "as_of": today,
        "age_as_of_jan1": age_jan1,
        "age_group": get_age_group(age_jan1),
        "total_matches": total_matches,
        "is_provisional": is_provisional,
        "provisional_matches_remaining": provisional_remaining,
        "tier": get_tier(float(row["current_rating"])),
        "confidence_ratio": round(cr, 4),
        "weeks_inactive": weeks_inactive,
        "inactivity_decay_active": weeks_inactive is not None and weeks_inactive >= 8,
    }


def get_academy_history(player_id: str) -> list | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM player WHERE player_id = %s", (player_id,))
            if not cur.fetchone():
                return None
            cur.execute(
                """
                SELECT h.history_id,
                       json_build_object(
                           'academy_id', a.academy_id, 'name', a.name,
                           'city', a.city, 'state', a.state
                       ) AS academy,
                       h.effective_from, h.effective_to, h.change_reason,
                       u.name AS changed_by
                FROM player_academy_history h
                JOIN academy a ON a.academy_id = h.academy_id
                LEFT JOIN users u ON u.user_id = h.changed_by_user_id
                WHERE h.player_id = %s
                ORDER BY h.effective_from DESC
                """,
                (player_id,),
            )
            return cur.fetchall()


def get_rating_history(
    player_id: str, show_breakdown: bool, limit: int, offset: int
) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM player WHERE player_id = %s", (player_id,))
            if not cur.fetchone():
                return None

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM rating_history WHERE player_id = %s",
                (player_id,),
            )
            total = cur.fetchone()["cnt"]

            cur.execute(
                """
                SELECT h.history_id, h.match_id,
                       h.rating_before, h.rating_after, h.delta,
                       h.delta_breakdown, h.tier_before, h.tier_after,
                       h.cr_before, h.cr_after, h.k_base, h.k_eff, h.k_shared,
                       h.expected_score, h.actual_score, h.age_bonus,
                       h.is_rollback, h.created_at,
                       m.match_date,
                       CASE WHEN m.winner_id = h.player_id THEN 'WIN' ELSE 'LOSS' END AS result,
                       opp.name AS opponent_name,
                       m.event_id::text AS event_id,
                       e.name AS event_name,
                       e.event_type::text AS event_type,
                       m.session_id::text AS session_id,
                       s.session_date,
                       m.match_category::text AS match_category,
                       m.sets_won_a,
                       m.sets_won_b,
                       m.confirmation_status::text AS confirmation_status,
                       m.diminishing_signal_applied,
                       opp_rh.rating_before::float AS opponent_rating_before
                FROM rating_history h
                JOIN match m ON m.match_id = h.match_id
                LEFT JOIN event e ON e.event_id = m.event_id
                LEFT JOIN session s ON s.session_id = m.session_id
                JOIN player opp ON opp.player_id = CASE
                    WHEN m.player_a_id = h.player_id THEN m.player_b_id
                    ELSE m.player_a_id
                END
                LEFT JOIN rating_history opp_rh
                    ON opp_rh.match_id = h.match_id
                    AND opp_rh.player_id = opp.player_id
                    AND opp_rh.is_rollback = FALSE
                WHERE h.player_id = %s
                ORDER BY m.match_date DESC, m.match_timestamp DESC, h.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (player_id, limit, offset),
            )
            rows = cur.fetchall()

    items = []
    for r in rows:
        entry = dict(r)
        if not show_breakdown:
            entry["delta_breakdown"] = None
        items.append(entry)

    return {"items": items, "total": total}


def transfer_academy(player_id: str, new_academy_id: str, effective_date: date) -> dict:
    """
    Raises LookupError if player not found.
    Raises ValueError if the 6-month transfer cooldown has not elapsed.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM player WHERE player_id = %s", (player_id,))
            if not cur.fetchone():
                raise LookupError("Player not found")

            cur.execute(
                """
                SELECT effective_from FROM player_academy_history
                WHERE player_id = %s AND effective_to IS NULL
                ORDER BY effective_from DESC LIMIT 1
                """,
                (player_id,),
            )
            current = cur.fetchone()
            if current:
                next_allowed = current["effective_from"] + relativedelta(months=6)
                if effective_date < next_allowed:
                    raise ValueError(f"Next transfer allowed after {next_allowed}")

            history_id = str(uuid.uuid4())
            cur.execute(
                "UPDATE player_academy_history SET effective_to = %s "
                "WHERE player_id = %s AND effective_to IS NULL",
                (effective_date, player_id),
            )
            cur.execute(
                """
                INSERT INTO player_academy_history
                    (history_id, player_id, academy_id, effective_from, change_reason)
                VALUES (%s, %s, %s, %s, 'TRANSFER')
                """,
                (history_id, player_id, new_academy_id, effective_date),
            )
            cur.execute(
                "UPDATE player SET primary_academy_id = %s WHERE player_id = %s",
                (new_academy_id, player_id),
            )
            next_change = effective_date + relativedelta(months=6)

    return {
        "player_id": player_id,
        "new_primary_academy_id": new_academy_id,
        "effective_date": effective_date,
        "next_change_allowed_after": next_change,
    }


def link_account(player_id: str, user_id: str) -> dict:
    """
    Links a player record to a user account (sets player.user_id).
    Raises LookupError if player or user not found.
    Raises ValueError if the user's role is not PLAYER, or if player already linked.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, user_id FROM player WHERE player_id = %s",
                (player_id,),
            )
            player = cur.fetchone()
            if not player:
                raise LookupError("Player not found")
            if player["user_id"] is not None:
                raise ValueError("Player is already linked to a user account")

            cur.execute(
                "SELECT user_id, role FROM users WHERE user_id = %s AND is_active = TRUE",
                (user_id,),
            )
            user = cur.fetchone()
            if not user:
                raise LookupError("User not found")
            if user["role"] != "PLAYER":
                raise ValueError("Only users with role PLAYER can be linked to a player record")

            cur.execute(
                "UPDATE player SET user_id = %s, updated_at = NOW() WHERE player_id = %s",
                (user_id, player_id),
            )
            cur.execute(_PLAYER_SELECT, (player_id,))
            return cur.fetchone()
