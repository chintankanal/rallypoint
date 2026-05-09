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

VALID_AGE_GROUPS = {"U10", "U13", "U15", "U17"}


def global_leaderboard(tier: str | None, limit: int, offset: int) -> dict:
    tier_filter = ""
    params_count: list = []
    params_page: list = []

    if tier:
        tier_filter = f"AND {_TIER_SQL} = %s"
        params_count.append(tier)
        params_page.append(tier)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM player p
                WHERE p.status = 'ACTIVE'
                  AND p.date_of_birth IS NOT NULL
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
                WHERE p.status = 'ACTIVE'
                  AND p.date_of_birth IS NOT NULL
                  {tier_filter}
                ORDER BY p.current_rating DESC
                LIMIT %s OFFSET %s
                """,
                params_page + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

    return {"total": total, "limit": limit, "offset": offset, "items": rows}


def age_group_leaderboard(age_group: str, limit: int, offset: int) -> dict:
    """Raises ValueError for unrecognised age_group values."""
    if age_group not in VALID_AGE_GROUPS:
        raise ValueError(f"age_group must be one of {sorted(VALID_AGE_GROUPS)}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH base AS (
                    SELECT
                        p.player_id::text, p.name, p.current_rating::float,
                        {_TIER_SQL} AS tier,
                        a.name AS academy_name,
                        {_AGE_JAN1_SQL} AS age_jan1,
                        {_AGE_GROUP_SQL} AS age_grp,
                        p.gender
                    FROM player p
                    LEFT JOIN academy a ON a.academy_id = p.primary_academy_id
                    WHERE p.status = 'ACTIVE' AND p.date_of_birth IS NOT NULL
                ),
                filtered AS (
                    SELECT *,
                        ROW_NUMBER() OVER (ORDER BY current_rating DESC) AS rank,
                        PERCENT_RANK() OVER (ORDER BY current_rating) AS percentile
                    FROM base
                    WHERE age_grp = %s
                )
                SELECT *, COUNT(*) OVER () AS total_count
                FROM filtered
                ORDER BY current_rating DESC
                LIMIT %s OFFSET %s
                """,
                (age_group, limit, offset),
            )
            rows = [dict(r) for r in cur.fetchall()]

    total = rows[0]["total_count"] if rows else 0
    return {"age_group": age_group, "total": total, "items": rows}
