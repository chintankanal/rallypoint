import uuid

from fastapi import HTTPException, status

from app.database import get_connection

_TIER_SQL = """
    CASE
        WHEN current_rating < 900  THEN 'BEGINNER'
        WHEN current_rating < 1100 THEN 'INTERMEDIATE'
        WHEN current_rating < 1300 THEN 'ADVANCED'
        WHEN current_rating < 1500 THEN 'ELITE'
        ELSE 'NATIONAL_TRACK'
    END
"""

_IS_PROVISIONAL_SQL = """
    (seeding_level = 'UNSEEDED' AND (rated_matches_completed + virtual_matches) < 15)
"""

_AGE_JAN1_SQL = """
    DATE_PART('year',
        AGE(MAKE_DATE(EXTRACT(YEAR FROM CURRENT_DATE)::int, 1, 1), date_of_birth)
    )::int
"""

_AGE_GROUP_SQL = f"""
    CASE
        WHEN {_AGE_JAN1_SQL} <= 10 THEN 'U10'
        WHEN {_AGE_JAN1_SQL} <= 13 THEN 'U13'
        WHEN {_AGE_JAN1_SQL} <= 15 THEN 'U15'
        WHEN {_AGE_JAN1_SQL} <= 17 THEN 'U17'
        ELSE 'OPEN'
    END
"""


def list_academies(status_filter: str | None = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status_filter:
                cur.execute(
                    "SELECT academy_id::text, name, city, state, status "
                    "FROM academy WHERE status = %s ORDER BY name",
                    (status_filter,),
                )
            else:
                cur.execute(
                    "SELECT academy_id::text, name, city, state, status FROM academy ORDER BY name"
                )
            return [dict(r) for r in cur.fetchall()]


def create_academy(body, created_by_id: str) -> dict:
    academy_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO academy (academy_id, name, location, city, state, min_tables, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING academy_id, name, location, city, state, status, min_tables, created_at
                """,
                (
                    academy_id,
                    body.name,
                    body.location,
                    body.city,
                    body.state,
                    body.min_tables,
                    created_by_id,
                    created_by_id,
                ),
            )
            return dict(cur.fetchone())


def get_academy(academy_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT academy_id, name, location, city, state, status, min_tables, created_at "
                "FROM academy WHERE academy_id = %s",
                (academy_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            cur.execute(
                """
                SELECT asi_value, qualifying_player_count, calculated_at
                FROM academy_asi_history
                WHERE academy_id = %s
                ORDER BY calculated_at DESC
                LIMIT 1
                """,
                (academy_id,),
            )
            asi_row = cur.fetchone()

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM player WHERE primary_academy_id = %s AND status = 'ACTIVE'",
                (academy_id,),
            )
            active_count = cur.fetchone()["cnt"]

    detail = dict(row)
    if asi_row:
        detail["current_asi"] = float(asi_row["asi_value"]) if asi_row["asi_value"] else None
        detail["asi_player_count"] = asi_row["qualifying_player_count"]
        detail["asi_last_calculated"] = asi_row["calculated_at"]
    else:
        detail["current_asi"] = None
        detail["asi_player_count"] = None
        detail["asi_last_calculated"] = None
    detail["active_player_count"] = active_count
    return detail


def academy_leaderboard(
    academy_id: str, tier: str | None, limit: int, offset: int
) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT academy_id FROM academy WHERE academy_id = %s", (academy_id,))
            if not cur.fetchone():
                return None

            tier_filter = ""
            params_count: list = [academy_id]
            params_page: list = [academy_id]

            if tier:
                tier_filter = f"AND {_TIER_SQL} = %s"
                params_count.append(tier)
                params_page.append(tier)

            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM player p
                WHERE p.primary_academy_id = %s
                  AND p.status = 'ACTIVE'
                  {tier_filter}
                """,
                params_count,
            )
            total = cur.fetchone()["cnt"]

            cur.execute(
                f"""
                SELECT
                    ROW_NUMBER() OVER (ORDER BY p.current_rating DESC) AS rank,
                    p.player_id::text, p.name, p.current_rating::float,
                    {_TIER_SQL} AS tier,
                    a.name AS academy_name,
                    {_IS_PROVISIONAL_SQL} AS is_provisional,
                    p.rated_matches_completed AS rated_matches,
                    p.last_match_date,
                    p.gender,
                    {_AGE_GROUP_SQL} AS age_group
                FROM player p
                LEFT JOIN academy a ON a.academy_id = p.primary_academy_id
                WHERE p.primary_academy_id = %s
                  AND p.status = 'ACTIVE'
                  {tier_filter}
                ORDER BY p.current_rating DESC
                LIMIT %s OFFSET %s
                """,
                params_page + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

    return {"total": total, "limit": limit, "offset": offset, "items": rows}


def get_asi_history(academy_id: str, limit: int) -> list[dict] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT academy_id FROM academy WHERE academy_id = %s", (academy_id,))
            if not cur.fetchone():
                return None
            cur.execute(
                """
                SELECT history_id, asi_value, qualifying_player_count,
                       calculation_basis, global_average_at_calculation, calculated_at
                FROM academy_asi_history
                WHERE academy_id = %s
                ORDER BY calculated_at DESC
                LIMIT %s
                """,
                (academy_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
