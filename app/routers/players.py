from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_roles
from app.services import player_service
from schemas.player import (
    AcademyTransferRequest,
    AcademyTransferResponse,
    LinkAccountRequest,
    PlayerAcademyHistoryEntry,
    PlayerAcademyHistoryResponse,
    PlayerComputedStats,
    PlayerCreate,
    PlayerResponse,
)
from schemas.rating import PaginatedRatingHistory, RatingHistoryEntry

router = APIRouter(prefix="/players", tags=["players"])

_ADMIN_COACH = Depends(require_roles("ADMIN", "COACH"))
_ANY_USER = Depends(get_current_user)


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
def create_player(body: PlayerCreate, current_user: dict = _ADMIN_COACH):
    row = player_service.create_player(body, current_user["user_id"])
    return PlayerResponse(**row)


@router.get("/search", tags=["players"])
def search_players(
    q: str = Query("", description="Name search"),
    academy_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    _: dict = _ANY_USER,
):
    """Search players by name — used by match submission forms."""
    items = player_service.search_players(q, academy_id, limit)
    return {"items": items}


@router.get("/{player_id}", response_model=PlayerResponse)
def get_player(player_id: str, _: dict = _ANY_USER):
    row = player_service.get_player(player_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PlayerResponse(**row)


@router.get("/{player_id}/computed-stats", response_model=PlayerComputedStats)
def get_computed_stats(player_id: str, _: dict = _ANY_USER):
    stats = player_service.get_computed_stats(player_id)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PlayerComputedStats(**stats)


@router.get("/{player_id}/academy-history", response_model=PlayerAcademyHistoryResponse)
def get_academy_history(player_id: str, _: dict = _ANY_USER):
    rows = player_service.get_academy_history(player_id)
    if rows is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    history = [PlayerAcademyHistoryEntry(**dict(r)) for r in rows]
    return PlayerAcademyHistoryResponse(player_id=player_id, history=history)


@router.patch("/{player_id}/academy", response_model=AcademyTransferResponse)
def transfer_academy(player_id: str, body: AcademyTransferRequest, _: dict = _ADMIN_COACH):
    try:
        result = player_service.transfer_academy(
            player_id, body.new_academy_id, body.effective_date
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return AcademyTransferResponse(**result)


@router.get("/{player_id}/rating-history", response_model=PaginatedRatingHistory)
def get_rating_history(
    player_id: str,
    current_user: dict = _ANY_USER,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    show_breakdown = (
        current_user["role"] in ("ADMIN", "COACH")
        or current_user.get("player_id") == player_id
    )
    result = player_service.get_rating_history(player_id, show_breakdown, limit, offset)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PaginatedRatingHistory(
        player_id=player_id,
        items=[RatingHistoryEntry(**r) for r in result["items"]],
        total=result["total"],
        limit=limit,
        offset=offset,
    )


@router.patch("/{player_id}/link-account", response_model=PlayerResponse)
def link_account(player_id: str, body: LinkAccountRequest, _: dict = _ADMIN_COACH):
    """Link a player record to an existing PLAYER-role user account."""
    try:
        row = player_service.link_account(player_id, body.user_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return PlayerResponse(**row)
