from app.database import get_connection
from app.utils.rating_math import _load_config


def _get_tier_sql() -> str:
    """Generate TIER CASE statement based on system config."""
    cfg = _load_config()
    beginner = int(cfg.get("tier_beginner_max", 899))
    intermediate = int(cfg.get("tier_intermediate_max", 1099))
    advanced = int(cfg.get("tier_advanced_max", 1299))
    elite = int(cfg.get("tier_elite_max", 1499))
    
    return f"""
    CASE
        WHEN current_rating <= {beginner}  THEN 'BEGINNER'
        WHEN current_rating <= {intermediate} THEN 'INTERMEDIATE'
        WHEN current_rating <= {advanced} THEN 'ADVANCED'
        WHEN current_rating <= {elite} THEN 'ELITE'
        ELSE 'NATIONAL_TRACK'
    END
"""


def _get_is_provisional_sql() -> str:
    """Generate IS_PROVISIONAL condition based on system config."""
    cfg = _load_config()
    threshold = int(cfg.get("provisional_threshold", 15))
    return f"(seeding_level = 'UNSEEDED' AND (rated_matches_completed + virtual_matches) < {threshold})"


def _get_age_jan1_sql() -> str:
    """Generate AGE_JAN1 calculation."""
    return """
    DATE_PART('year',
        AGE(MAKE_DATE(EXTRACT(YEAR FROM CURRENT_DATE)::int, 1, 1), date_of_birth)
    )::int
"""


def _get_age_group_sql() -> str:
    """Generate AGE_GROUP CASE statement based on system config."""
    cfg = _load_config()
    u11 = int(cfg.get("age_group_u11_max", cfg.get("age_group_u10_max", 11)))
    u13 = int(cfg.get("age_group_u13_max", 13))
    u15 = int(cfg.get("age_group_u15_max", 15))
    u17 = int(cfg.get("age_group_u17_max", 17))
    
    age_jan1_sql = _get_age_jan1_sql().strip()
    
    return f"""
    CASE
        WHEN {age_jan1_sql} <= {u11} THEN 'U11'
        WHEN {age_jan1_sql} <= {u13} THEN 'U13'
        WHEN {age_jan1_sql} <= {u15} THEN 'U15'
        WHEN {age_jan1_sql} <= {u17} THEN 'U17'
        ELSE 'OPEN'
    END
"""


_TIER_SQL = _get_tier_sql()
_IS_PROVISIONAL_SQL = _get_is_provisional_sql()
_AGE_JAN1_SQL = _get_age_jan1_sql()
_AGE_GROUP_SQL = _get_age_group_sql()

VALID_AGE_GROUPS = {"U11", "U13", "U15", "U17"}


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
                    ROW_NUMBER() OVER (
                        ORDER BY a.name ASC NULLS LAST, p.current_rating DESC, {_AGE_JAN1_SQL} ASC NULLS LAST
                    ) AS rank,
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
                ORDER BY a.name ASC NULLS LAST, p.current_rating DESC, {_AGE_JAN1_SQL} ASC NULLS LAST
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
                        ROW_NUMBER() OVER (ORDER BY academy_name ASC NULLS LAST, current_rating DESC) AS rank,
                        PERCENT_RANK() OVER (ORDER BY current_rating) AS percentile
                    FROM base
                    WHERE age_grp = %s
                )
                SELECT *, COUNT(*) OVER () AS total_count
                FROM filtered
                ORDER BY academy_name ASC NULLS LAST, current_rating DESC
                LIMIT %s OFFSET %s
                """,
                (age_group, limit, offset),
            )
            rows = [dict(r) for r in cur.fetchall()]

    total = rows[0]["total_count"] if rows else 0
    return {"age_group": age_group, "total": total, "items": rows}
