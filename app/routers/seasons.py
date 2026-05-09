from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import require_roles
from app.services import season_service
from schemas.season import SeasonCreate, SeasonResponse, SeasonStatusUpdate

router = APIRouter(prefix="/seasons", tags=["seasons"])

_ADMIN = Depends(require_roles("ADMIN"))


@router.post("", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
def create_season(body: SeasonCreate, _: dict = _ADMIN):
    return SeasonResponse(**season_service.create_season(body))


@router.get("", response_model=list[SeasonResponse])
def list_seasons(_: dict = _ADMIN):
    return [SeasonResponse(**r) for r in season_service.list_seasons()]


@router.patch("/{season_id}/status", response_model=SeasonResponse)
def update_season_status(season_id: str, body: SeasonStatusUpdate, _: dict = _ADMIN):
    row = season_service.update_season_status(season_id, body.status.value)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return SeasonResponse(**row)
