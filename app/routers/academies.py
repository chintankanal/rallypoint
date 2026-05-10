from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_roles
from app.services import academy_service
from schemas.academy import AcademyCreate, AcademyDetail, AcademyResponse, AcademyStats, TierDistribution
from schemas.leaderboard import (
    ASIHistoryEntry,
    ASIHistoryResponse,
    LeaderboardEntry,
    LeaderboardResponse,
)

router = APIRouter(prefix="/academies", tags=["academies"])

_ADMIN = Depends(require_roles("ADMIN"))
_ANY_USER = Depends(get_current_user)


@router.get("", tags=["academies"])
def list_academies(status_filter: str | None = Query(None, alias="status")):
    """Public list — used by registration and admin forms."""
    return {"items": academy_service.list_academies(status_filter)}


@router.post("", response_model=AcademyResponse, status_code=status.HTTP_201_CREATED)
def create_academy(body: AcademyCreate, current_user: dict = _ADMIN):
    return AcademyResponse(**academy_service.create_academy(body, current_user["user_id"]))


@router.get("/{academy_id}", response_model=AcademyDetail)
def get_academy(academy_id: str, _: dict = _ANY_USER):
    detail = academy_service.get_academy(academy_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academy not found")
    return AcademyDetail(**detail)


@router.get("/{academy_id}/leaderboard", response_model=LeaderboardResponse)
def academy_leaderboard(
    academy_id: str,
    tier: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: dict = _ANY_USER,
):
    result = academy_service.academy_leaderboard(academy_id, tier, limit, offset)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academy not found")
    items = [
        LeaderboardEntry(
            rank=r["rank"],
            player_id=r["player_id"],
            name=r["name"],
            current_rating=float(r["current_rating"]),
            tier=r["tier"],
            academy_name=r.get("academy_name"),
            is_provisional=r["is_provisional"],
            rated_matches=r["rated_matches"],
            last_match_date=r.get("last_match_date"),
            gender=r.get("gender"),
            age_group=r.get("age_group"),
        )
        for r in result["items"]
    ]
    return LeaderboardResponse(
        total=result["total"], limit=result["limit"], offset=result["offset"], items=items
    )


@router.get("/{academy_id}/asi-history", response_model=ASIHistoryResponse)
def get_asi_history(
    academy_id: str,
    limit: int = Query(12, ge=1, le=100),
    _: dict = _ANY_USER,
):
    rows = academy_service.get_asi_history(academy_id, limit)
    if rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academy not found")
    items = [
        ASIHistoryEntry(
            history_id=str(r["history_id"]),
            asi_value=float(r["asi_value"]) if r["asi_value"] is not None else None,
            qualifying_player_count=r["qualifying_player_count"],
            calculation_basis=r["calculation_basis"],
            global_average_at_calculation=float(r["global_average_at_calculation"]),
            calculated_at=r["calculated_at"],
        )
        for r in rows
    ]
    return ASIHistoryResponse(academy_id=academy_id, items=items)


@router.get("/{academy_id}/stats", response_model=AcademyStats)
def get_academy_stats(
    academy_id: str,
    _: dict = _ANY_USER,
):
    """Get comprehensive statistics for an academy including player counts, match volume, and tier distribution."""
    stats = academy_service.get_academy_stats(academy_id)
    if stats is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academy not found")
    
    return AcademyStats(
        academy_id=academy_id,
        tables_available=stats["tables_available"],
        active_player_count=stats["active_player_count"],
        coach_count=stats["coach_count"],
        total_match_volume=stats["total_match_volume"],
        matches_30_days=stats["matches_30_days"],
        current_asi=stats["current_asi"],
        tier_distribution=TierDistribution(**stats["tier_distribution"]),
    )
