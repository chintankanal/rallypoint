import uuid

from app.database import get_connection
from app.services.rating_engine import apply_ratings_batch
from app.services.webhook_service import fire


def _fetch_event(cur, event_id: str) -> dict | None:
    cur.execute(
        """
        SELECT e.event_id, e.name, e.scheduling_mode, e.event_type,
               e.default_match_format, e.tournament_format, e.status,
               e.start_date, e.end_date, e.created_at,
               CASE WHEN e.season_id IS NOT NULL THEN
                   json_build_object('season_id', s.season_id, 'name', s.name)
               ELSE NULL END AS season,
               COALESCE(
                   (
                       SELECT json_agg(json_build_object('academy_id', a.academy_id, 'name', a.name))
                       FROM event_academy ea
                       JOIN academy a ON a.academy_id = ea.academy_id
                       WHERE ea.event_id = e.event_id
                   ),
                   '[]'::json
               ) AS participating_academies
        FROM event e
        LEFT JOIN season s ON s.season_id = e.season_id
        WHERE e.event_id = %s
        """,
        (event_id,),
    )
    return cur.fetchone()


def create_event(body, creator_role: str, creator_academy_id: str | None, created_by: str) -> dict:
    """
    Raises ValueError if a COACH tries to create a non-INTRA_ACADEMY event.
    """
    if creator_role == "COACH" and body.scheduling_mode.value != "INTRA_ACADEMY":
        raise ValueError("Coaches may only create INTRA_ACADEMY events")

    event_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event (
                    event_id, season_id, name, scheduling_mode, event_type,
                    default_match_format, tournament_format, host_academy_id,
                    start_date, end_date, created_by, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event_id,
                    body.season_id,
                    body.name,
                    body.scheduling_mode.value,
                    body.event_type.value,
                    body.default_match_format.value if body.default_match_format else None,
                    body.tournament_format.value if body.tournament_format else None,
                    body.host_academy_id,
                    body.start_date,
                    body.end_date,
                    created_by,
                    created_by,
                ),
            )
            for academy_id in body.participating_academy_ids:
                cur.execute(
                    "INSERT INTO event_academy (event_id, academy_id) VALUES (%s, %s)",
                    (event_id, academy_id),
                )
            row = _fetch_event(cur, event_id)
    return dict(row)


def list_events(role: str, academy_id: str | None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if role == "ADMIN":
                cur.execute(
                    """
                    SELECT e.event_id::text, e.name, e.scheduling_mode, e.event_type,
                           e.status, e.start_date, e.end_date
                    FROM event e ORDER BY e.start_date DESC LIMIT 100
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT DISTINCT e.event_id::text, e.name, e.scheduling_mode, e.event_type,
                           e.status, e.start_date, e.end_date
                    FROM event e
                    LEFT JOIN event_academy ea ON ea.event_id = e.event_id
                    WHERE e.host_academy_id = %s OR ea.academy_id = %s
                    ORDER BY e.start_date DESC LIMIT 100
                    """,
                    (academy_id, academy_id),
                )
            return [dict(r) for r in cur.fetchall()]


def get_event(event_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            row = _fetch_event(cur, event_id)
    return dict(row) if row else None


def add_academy_to_event(event_id: str, academy_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT event_id FROM event WHERE event_id = %s", (event_id,))
            if not cur.fetchone():
                return None
            cur.execute(
                "INSERT INTO event_academy (event_id, academy_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (event_id, academy_id),
            )
            row = _fetch_event(cur, event_id)
    return dict(row)


def update_event_status(event_id: str, new_status: str) -> dict | None:
    """
    Returns the updated event dict, or None if not found.
    Raises ValueError listing open dispute IDs when trying to COMPLETE an event that has unresolved disputes.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_id, scheduling_mode FROM event WHERE event_id = %s",
                (event_id,),
            )
            event = cur.fetchone()
            if not event:
                return None

            if new_status == "COMPLETED":
                cur.execute(
                    """
                    SELECT d.dispute_id FROM dispute d
                    JOIN match m ON m.match_id = d.match_id
                    WHERE m.event_id = %s AND d.status NOT IN ('RESOLVED', 'EXPIRED')
                    """,
                    (event_id,),
                )
                open_disputes = cur.fetchall()
                if open_disputes:
                    ids = [r["dispute_id"] for r in open_disputes]
                    raise ValueError(
                        {"message": "Open disputes must be resolved first", "dispute_ids": ids}
                    )

                if event["scheduling_mode"] == "INTER_ACADEMY":
                    cur.execute(
                        """
                        SELECT match_id FROM match
                        WHERE event_id = %s
                          AND rating_eligible = TRUE
                          AND ratings_applied_at IS NULL
                          AND confirmation_status IN ('CONFIRMED', 'AUTO_CONFIRMED')
                        """,
                        (event_id,),
                    )
                    eligible_ids = [r["match_id"] for r in cur.fetchall()]
                    if eligible_ids:
                        tier_changes = apply_ratings_batch(conn, eligible_ids)
                        for tc in tier_changes:
                            fire("player.tier_changed", tc)

            cur.execute(
                "UPDATE event SET status = %s WHERE event_id = %s",
                (new_status, event_id),
            )
            row = _fetch_event(cur, event_id)
    return dict(row)


def assign_referee(event_id: str, user_id: str) -> dict | None:
    assignment_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT event_id FROM event WHERE event_id = %s", (event_id,))
            if not cur.fetchone():
                return None
            cur.execute(
                """
                INSERT INTO event_referee (assignment_id, event_id, user_id)
                VALUES (%s, %s, %s)
                RETURNING assignment_id, event_id, user_id, assigned_at
                """,
                (assignment_id, event_id, user_id),
            )
            return dict(cur.fetchone())


def assign_umpire(event_id: str, user_id: str, table_number: int | None) -> dict | None:
    assignment_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT event_id FROM event WHERE event_id = %s", (event_id,))
            if not cur.fetchone():
                return None
            cur.execute(
                """
                INSERT INTO event_umpire (assignment_id, event_id, user_id, table_number)
                VALUES (%s, %s, %s, %s)
                RETURNING assignment_id, event_id, user_id, table_number, assigned_at
                """,
                (assignment_id, event_id, user_id, table_number),
            )
            return dict(cur.fetchone())
