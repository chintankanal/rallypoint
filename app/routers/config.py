import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_connection
from app.dependencies.auth import get_current_user, require_roles
from schemas.leaderboard import (
    ConfigEntry,
    ConfigHistoryEntry,
    ConfigHistoryResponse,
    ConfigResponse,
    ConfigUpdate,
)

router = APIRouter(prefix="/config", tags=["config"])

_ADMIN = Depends(require_roles("ADMIN"))
_ANY = Depends(get_current_user)

# Keys exposed to non-admin roles
_PUBLIC_KEYS = {
    "k_base_provisional",
    "k_base_developing",
    "k_base_established",
    "match_weight_league",
    "match_weight_tournament",
    "match_weight_friendly",
    "academy_weight_same",
    "academy_weight_cross",
    "competitive_max_gap",
    "stretch_max_gap",
    "provisional_match_threshold",
}


@router.get("", response_model=ConfigResponse)
def get_config(current_user: dict = _ANY):
    role = current_user.get("role", "PLAYER")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key, value, description FROM system_configuration ORDER BY key"
            )
            rows = [dict(r) for r in cur.fetchall()]

    if role != "ADMIN":
        rows = [r for r in rows if r["key"] in _PUBLIC_KEYS]

    return ConfigResponse(
        items=[
            ConfigEntry(key=r["key"], value=r["value"], description=r.get("description"))
            for r in rows
        ]
    )


@router.patch("/{key}", response_model=ConfigEntry)
def update_config(key: str, body: ConfigUpdate, current_user: dict = _ADMIN):
    user_id = current_user["user_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key, value, description FROM system_configuration WHERE key = %s",
                (key,),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Config key '{key}' not found",
                )

            old_value = existing["value"]
            cur.execute(
                """
                UPDATE system_configuration
                SET value = %s, updated_by = %s, updated_at = NOW()
                WHERE key = %s
                """,
                (body.value, user_id, key),
            )
            cur.execute(
                """
                INSERT INTO system_configuration_history
                    (history_id, key, old_value, new_value, changed_by, effective_for_matches_after)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (str(uuid.uuid4()), key, old_value, body.value, user_id),
            )

    from app.services.rating_engine import invalidate_config_cache
    invalidate_config_cache()

    return ConfigEntry(key=key, value=body.value, description=existing["description"])


@router.get("/history", response_model=ConfigHistoryResponse)
def get_config_history(
    key: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    _: dict = _ADMIN,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if key:
                cur.execute(
                    """
                    SELECT history_id, key, old_value, new_value, changed_at
                    FROM system_configuration_history
                    WHERE key = %s
                    ORDER BY changed_at DESC
                    LIMIT %s
                    """,
                    (key, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT history_id, key, old_value, new_value, changed_at
                    FROM system_configuration_history
                    ORDER BY changed_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = [dict(r) for r in cur.fetchall()]

            if key:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM system_configuration_history WHERE key = %s",
                    (key,),
                )
            else:
                cur.execute("SELECT COUNT(*) AS cnt FROM system_configuration_history")
            total = cur.fetchone()["cnt"]

    return ConfigHistoryResponse(
        key=key,
        total=total,
        items=[
            ConfigHistoryEntry(
                history_id=str(r["history_id"]),
                key=r["key"],
                old_value=r["old_value"],
                new_value=r["new_value"],
                changed_at=r["changed_at"],
            )
            for r in rows
        ],
    )
