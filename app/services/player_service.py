import secrets
import string
import uuid
from datetime import date

from dateutil.relativedelta import relativedelta

from app.database import get_connection
from app.utils.rating_math import get_age_as_of_jan1, get_age_group, get_cr, get_tier, _load_config

# Default fallbacks (used if config unavailable)
_SEEDING_DEFAULTS: dict[str, tuple[float, int]] = {
    "UNSEEDED": (1000.0, 0),
    "DISTRICT": (1200.0, 10),
    "STATE":    (1400.0, 20),
    "NATIONAL": (1500.0, 30),
}


def _get_seeding_defaults() -> dict[str, tuple[float, int]]:
    """Load seeding defaults from config, with fallback to hardcoded values."""
    try:
        cfg = _load_config()
        return {
            "UNSEEDED": (
                cfg.get("starting_rating_unseeded", 1000.0),
                int(cfg.get("virtual_matches_unseeded", 0))
            ),
            "DISTRICT": (
                cfg.get("starting_rating_district", 1200.0),
                int(cfg.get("virtual_matches_district", 10))
            ),
            "STATE": (
                cfg.get("starting_rating_state", 1400.0),
                int(cfg.get("virtual_matches_state", 20))
            ),
            "NATIONAL": (
                cfg.get("starting_rating_national", 1500.0),
                int(cfg.get("virtual_matches_national", 30))
            ),
        }
    except Exception:
        return _SEEDING_DEFAULTS.copy()

_PLAYER_SELECT = """
    SELECT p.player_id, p.name, p.date_of_birth, p.gender, p.nationality,
           p.current_rating, p.rated_matches_completed,
           p.virtual_matches, p.seeding_level, p.seeding_reference, p.last_match_date, p.status,
           p.guardian_name, p.guardian_phone, p.contact_email,
           p.is_claimed, p.claim_code, p.created_at,
           json_build_object(
               'academy_id', a.academy_id, 'name', a.name,
               'city', a.city, 'state', a.state
           ) AS primary_academy
    FROM player p
    JOIN academy a ON a.academy_id = p.primary_academy_id
    WHERE p.player_id = %s
"""


def create_player(body, created_by_id: str) -> dict:
    seeding_defaults = _get_seeding_defaults()
    starting_rating, default_virtual = seeding_defaults.get(
        body.seeding_level.value, (1000.0, 0)
    )
    virtual_matches = body.virtual_matches if body.virtual_matches is not None else default_virtual

    player_id = str(uuid.uuid4())
    history_id = str(uuid.uuid4())

    def _generate_claim_code() -> str:
        alphabet = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(8))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT player_id FROM player
                WHERE lower(name) = lower(%s)
                  AND date_of_birth = %s
                  AND primary_academy_id = %s
                  AND guardian_name IS NOT DISTINCT FROM %s
                  AND guardian_phone IS NOT DISTINCT FROM %s
                  AND contact_email IS NOT DISTINCT FROM %s
                """,
                (
                    body.name,
                    body.date_of_birth,
                    body.primary_academy_id,
                    body.guardian_name,
                    body.guardian_phone,
                    body.contact_email,
                ),
            )
            if cur.fetchone() is not None:
                raise ValueError(
                    "Player with same name, date of birth, academy, and contact information already exists"
                )

            claim_code = _generate_claim_code()
            cur.execute(
                "SELECT 1 FROM player WHERE claim_code = %s",
                (claim_code,),
            )
            while cur.fetchone() is not None:
                claim_code = _generate_claim_code()
                cur.execute(
                    "SELECT 1 FROM player WHERE claim_code = %s",
                    (claim_code,),
                )

            cur.execute(
                """
                INSERT INTO player (
                    player_id, name, date_of_birth, gender, nationality,
                    primary_academy_id, seeding_level, seeding_reference,
                    virtual_matches, current_rating,
                    guardian_name, guardian_phone, contact_email,
                    claim_code, is_claimed,
                    created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    claim_code,
                    False,
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


def update_player(
    player_id: str,
    body,
    caller_academy_id: str | None,
    caller_role: str,
    updated_by_id: str = "",
) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT primary_academy_id, rated_matches_completed FROM player WHERE player_id = %s",
                (player_id,),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError("Player not found")

            if caller_role == 'COACH':
                if not caller_academy_id or row['primary_academy_id'] != caller_academy_id:
                    raise PermissionError("Coaches can only edit players in their own academy")

            if (body.current_rating is not None or body.virtual_matches is not None) and row['rated_matches_completed'] != 0:
                raise ValueError(
                    "Current rating and virtual matches can only be updated before any rated matches have been completed"
                )

            updates: list[str] = []
            params: list = []
            if body.name is not None:
                updates.append('name = %s')
                params.append(body.name)
            if body.date_of_birth is not None:
                updates.append('date_of_birth = %s')
                params.append(body.date_of_birth)
            if body.gender is not None:
                updates.append('gender = %s')
                params.append(body.gender.value)
            if body.nationality is not None:
                updates.append('nationality = %s')
                params.append(body.nationality)
            if 'guardian_name' in body.model_fields_set:
                updates.append('guardian_name = %s')
                params.append(body.guardian_name)
            if 'guardian_phone' in body.model_fields_set:
                updates.append('guardian_phone = %s')
                params.append(body.guardian_phone)
            if 'contact_email' in body.model_fields_set:
                updates.append('contact_email = %s')
                params.append(body.contact_email)
            if body.seeding_level is not None:
                updates.append('seeding_level = %s')
                params.append(body.seeding_level.value)
            if 'seeding_reference' in body.model_fields_set:
                updates.append('seeding_reference = %s')
                params.append(body.seeding_reference)
            if body.current_rating is not None:
                updates.append('current_rating = %s')
                params.append(body.current_rating)
            if body.virtual_matches is not None:
                updates.append('virtual_matches = %s')
                params.append(body.virtual_matches)

            if not updates:
                raise ValueError('No valid fields provided for player update')

            updates.append('updated_by = %s')
            params.append(updated_by_id)
            updates.append('updated_at = NOW()')
            params.append(player_id)
            cur.execute(
                f"UPDATE player SET {', '.join(updates)} WHERE player_id = %s",
                params,
            )
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


def list_all_players() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.player_id::text, p.name, p.current_rating::float,
                       p.status,
                       p.primary_academy_id::text AS academy_id,
                       a.name AS academy_name
                FROM player p
                JOIN academy a ON a.academy_id = p.primary_academy_id
                ORDER BY a.name, p.name
                """
            )
            return [dict(r) for r in cur.fetchall()]


def claim_player(user_id: str, claim_code: str) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_id, user_id, is_claimed, primary_academy_id FROM player WHERE claim_code = %s",
                (claim_code,),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError("Claim code not found")
            if row["is_claimed"] or row["user_id"] is not None:
                raise ValueError("Player record has already been claimed")

            cur.execute(
                "UPDATE player SET user_id = %s, is_claimed = TRUE, updated_at = CURRENT_TIMESTAMP WHERE player_id = %s RETURNING player_id",
                (user_id, row["player_id"]),
            )
            updated = cur.fetchone()
            if not updated:
                raise LookupError("Failed to claim player")

            if row["primary_academy_id"]:
                cur.execute(
                    "UPDATE users SET academy_id = %s WHERE user_id = %s",
                    (row["primary_academy_id"], user_id),
                )

            cur.execute(_PLAYER_SELECT, (row["player_id"],))
            return cur.fetchone()


def _get_player_role_exposure(cur, player_id: str, period_days: int = 90) -> dict[str, int]:
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE (m.player_a_id = %s AND m.player_a_role = 'PEER')
                                OR (m.player_b_id = %s AND m.player_b_role = 'PEER')) AS as_peer,
            COUNT(*) FILTER (WHERE (m.player_a_id = %s AND m.player_a_role = 'ANCHORING')
                                OR (m.player_b_id = %s AND m.player_b_role = 'ANCHORING')) AS as_anchoring,
            COUNT(*) FILTER (WHERE (m.player_a_id = %s AND m.player_a_role = 'STRETCHING')
                                OR (m.player_b_id = %s AND m.player_b_role = 'STRETCHING')) AS as_stretching,
            COUNT(*) FILTER (WHERE (m.player_a_id = %s AND m.player_a_role = 'BYE')
                                OR (m.player_b_id = %s AND m.player_b_role = 'BYE')) AS bye_count
        FROM match m
        WHERE (m.player_a_id = %s OR m.player_b_id = %s)
          AND m.confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')
          AND m.match_date >= CURRENT_DATE - (%s || ' days')::interval
        """,
        (
            player_id, player_id,
            player_id, player_id,
            player_id, player_id,
            player_id, player_id,
            player_id, player_id, str(period_days),
        ),
    )
    row = cur.fetchone()
    if not row:
        return {"as_peer": 0, "as_anchoring": 0, "as_stretching": 0, "bye_count": 0}
    # All columns are guaranteed by the SQL; use strict indexing to surface schema drift
    return {
        "as_peer": int(row["as_peer"]),
        "as_anchoring": int(row["as_anchoring"]),
        "as_stretching": int(row["as_stretching"]),
        "bye_count": int(row["bye_count"]),
    }


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
            role_exposure = _get_player_role_exposure(cur, player_id)

    from app.utils.rating_math import _load_config
    cfg = _load_config()

    today = date.today()
    total_matches = row["rated_matches_completed"] + row["virtual_matches"]
    age_jan1 = get_age_as_of_jan1(row["date_of_birth"])
    cr = get_cr(total_matches, cfg)
    
    prov_threshold = int(cfg.get("provisional_threshold", 15))
    is_provisional = row["seeding_level"] == "UNSEEDED" and total_matches < prov_threshold
    provisional_remaining = max(0, prov_threshold - total_matches) if is_provisional else 0

    weeks_inactive: float | None = None
    if row["last_match_date"]:
        weeks_inactive = round((today - row["last_match_date"]).days / 7, 2)

    return {
        "player_id": player_id,
        "as_of": today,
        "age_as_of_jan1": age_jan1,
        "age_group": get_age_group(age_jan1, cfg),
        "total_matches": total_matches,
        "is_provisional": is_provisional,
        "provisional_matches_remaining": provisional_remaining,
        "tier": get_tier(float(row["current_rating"]), cfg),
        "confidence_ratio": round(cr, 4),
        "weeks_inactive": weeks_inactive,
        "inactivity_decay_active": weeks_inactive is not None and weeks_inactive >= 8,
        "role_exposure": role_exposure,
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


def get_player_event_fixtures(player_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM player WHERE player_id = %s", (player_id,))
            if not cur.fetchone():
                return None

            cur.execute(
                """
                SELECT e.event_id::text, e.name, e.scheduling_mode, e.event_type,
                       e.status, e.fixture_state, e.start_date, e.end_date,
                       e.default_match_format
                FROM event e
                JOIN event_player_registration epr ON epr.event_id = e.event_id
                WHERE epr.player_id = %s
                  AND epr.status IN ('REGISTERED', 'CHECKED_IN')
                  AND e.status IN ('SCHEDULED', 'IN_PROGRESS')
                ORDER BY e.start_date, e.name
                """,
                (player_id,),
            )
            events = [dict(r) for r in cur.fetchall()]
            if not events:
                return {"player_id": player_id, "items": []}

            event_ids = [str(ev["event_id"]) for ev in events]
            cur.execute(
                """
                SELECT efs.event_id::text, efs.slot_id::text, efs.round_number, efs.table_number,
                       efs.match_category, efs.expected_rating_gap, efs.status, efs.match_id::text,
                       efs.fixture_strategy,
                       efs.player_a_id::text, pa.name AS player_a_name,
                       pa.current_rating AS player_a_rating,
                       pa.primary_academy_id::text AS player_a_academy_id,
                       aa.name AS player_a_academy_name,
                       efs.player_b_id::text, pb.name AS player_b_name,
                       pb.current_rating AS player_b_rating,
                       pb.primary_academy_id::text AS player_b_academy_id,
                       ab.name AS player_b_academy_name
                FROM event_fixture_slot efs
                JOIN player pa ON pa.player_id = efs.player_a_id
                JOIN academy aa ON aa.academy_id = pa.primary_academy_id
                LEFT JOIN player pb ON pb.player_id = efs.player_b_id
                LEFT JOIN academy ab ON ab.academy_id = pb.primary_academy_id
                WHERE efs.event_id = ANY(%s::uuid[])
                  AND (efs.player_a_id = %s OR efs.player_b_id = %s)
                ORDER BY efs.event_id, efs.round_number, efs.table_number
                """,
                (event_ids, player_id, player_id),
            )
            rows = [dict(r) for r in cur.fetchall()]

    slots_by_event: dict[str, list[dict]] = {}
    for row in rows:
        slot = {
            "slot_id": row["slot_id"],
            "round_number": row["round_number"],
            "table_number": row["table_number"],
            "match_category": row["match_category"],
            "expected_rating_gap": float(row["expected_rating_gap"]),
            "status": row["status"],
            "fixture_strategy": row["fixture_strategy"],
            "match_id": row["match_id"],
            "player_a": {
                "player_id": row["player_a_id"],
                "name": row["player_a_name"],
                "current_rating": float(row["player_a_rating"]),
                "academy_id": row["player_a_academy_id"],
                "academy_name": row["player_a_academy_name"],
            },
            "player_b": {
                "player_id": row["player_b_id"],
                "name": row["player_b_name"],
                "current_rating": float(row["player_b_rating"]),
                "academy_id": row["player_b_academy_id"],
                "academy_name": row["player_b_academy_name"],
            } if row["player_b_id"] else None,
        }
        slots_by_event.setdefault(row["event_id"], []).append(slot)

    return {
        "player_id": player_id,
        "items": [
            {
                "event_id": ev["event_id"],
                "name": ev["name"],
                "scheduling_mode": ev["scheduling_mode"],
                "event_type": ev["event_type"],
                "status": ev["status"],
                "fixture_state": ev["fixture_state"],
                "start_date": ev["start_date"],
                "end_date": ev["end_date"],
                "default_match_format": ev["default_match_format"],
                "slots": slots_by_event.get(ev["event_id"], []),
            }
            for ev in events
        ],
    }


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
                "SELECT player_id, user_id, primary_academy_id FROM player WHERE player_id = %s",
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
                "UPDATE player SET user_id = %s, is_claimed = TRUE, updated_at = NOW() WHERE player_id = %s",
                (user_id, player_id),
            )
            if player["primary_academy_id"]:
                cur.execute(
                    "UPDATE users SET academy_id = %s WHERE user_id = %s",
                    (player["primary_academy_id"], user_id),
                )
            cur.execute(_PLAYER_SELECT, (player_id,))
            return cur.fetchone()
