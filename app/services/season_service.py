import uuid

from app.database import get_connection


def create_season(body) -> dict:
    season_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO season (season_id, name, start_date, end_date)
                VALUES (%s, %s, %s, %s)
                RETURNING season_id, name, start_date, end_date, status, created_at
                """,
                (season_id, body.name, body.start_date, body.end_date),
            )
            return dict(cur.fetchone())


def list_seasons() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT season_id, name, start_date, end_date, status, created_at "
                "FROM season ORDER BY start_date DESC"
            )
            return [dict(r) for r in cur.fetchall()]


def update_season_status(season_id: str, new_status: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE season SET status = %s
                WHERE season_id = %s
                RETURNING season_id, name, start_date, end_date, status, created_at
                """,
                (new_status, season_id),
            )
            row = cur.fetchone()
    return dict(row) if row else None
