import uuid

from fastapi import HTTPException, status

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
                    {_AGE_GROUP_SQL} AS age_group,
                    p.claim_code,
                    p.is_claimed
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


def get_academy_stats(academy_id: str) -> dict | None:
    """Get comprehensive statistics for an academy."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verify academy exists
            cur.execute("SELECT academy_id FROM academy WHERE academy_id = %s", (academy_id,))
            if not cur.fetchone():
                return None
            
            stats = {}
            
            # 1. Tables available (from system_configuration key-value store)
            cur.execute(
                "SELECT value FROM system_configuration WHERE key = 'total_tables'"
            )
            result = cur.fetchone()
            stats["tables_available"] = int(result["value"]) if result else 0
            
            # 2. Active Player Count
            cur.execute(
                """
                SELECT COUNT(*) as count FROM player
                WHERE primary_academy_id = %s AND status = 'ACTIVE'
                """,
                (academy_id,)
            )
            stats["active_player_count"] = cur.fetchone()["count"]
            
            # 3. Coach Count
            cur.execute(
                """
                SELECT COUNT(*) as count FROM users
                WHERE academy_id = %s AND role = 'COACH'
                """,
                (academy_id,)
            )
            stats["coach_count"] = cur.fetchone()["count"]
            
            # 4. Total Match Volume (historical)
            cur.execute(
                """
                SELECT COUNT(*) as count FROM match
                WHERE player_a_academy_id = %s OR player_b_academy_id = %s
                """,
                (academy_id, academy_id)
            )
            stats["total_match_volume"] = cur.fetchone()["count"]
            
            # 5. 30-Day Activity
            cur.execute(
                """
                SELECT COUNT(*) as count FROM match
                WHERE (player_a_academy_id = %s OR player_b_academy_id = %s)
                  AND match_date >= CURRENT_DATE - INTERVAL '30 days'
                """,
                (academy_id, academy_id)
            )
            stats["matches_30_days"] = cur.fetchone()["count"]
            
            # 6. Current ASI (mean rating of top non-provisional players)
            cur.execute(
                f"""
                SELECT current_rating
                FROM player
                WHERE primary_academy_id = %s
                  AND status = 'ACTIVE'
                  AND NOT ({_IS_PROVISIONAL_SQL})
                  AND current_rating >= 1000
                ORDER BY current_rating DESC
                LIMIT 15
                """,
                (academy_id,)
            )
            rows = cur.fetchall()
            if rows:
                asi_value = sum(row["current_rating"] for row in rows) / len(rows)
                stats["current_asi"] = float(asi_value)
            else:
                stats["current_asi"] = None
            
            # 7. Tier Distribution
            cur.execute(
                f"""
                SELECT
                    {_TIER_SQL} as tier,
                    COUNT(*) as player_count
                FROM player
                WHERE primary_academy_id = %s AND status = 'ACTIVE'
                GROUP BY {_TIER_SQL}
                """,
                (academy_id,)
            )
            
            tier_distribution = {
                "BEGINNER": 0,
                "INTERMEDIATE": 0,
                "ADVANCED": 0,
                "ELITE": 0,
                "NATIONAL_TRACK": 0
            }
            
            for row in cur.fetchall():
                tier_distribution[row["tier"]] = row["player_count"]
            
            stats["tier_distribution"] = tier_distribution
            
    return stats
