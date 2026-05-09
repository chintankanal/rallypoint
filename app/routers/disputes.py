from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_roles
from app.services import dispute_service
from schemas.dispute import (
    DisputeResolveRequest,
    DisputeResponse,
    DisputeStatusUpdate,
    PaginatedDisputeResponse,
)

router = APIRouter(prefix="/disputes", tags=["disputes"])

_ANY_USER = Depends(get_current_user)
_ADMIN_REFEREE = Depends(require_roles("ADMIN", "REFEREE"))


@router.get("", response_model=PaginatedDisputeResponse)
def list_disputes(
    _: dict = _ANY_USER,
    dispute_status: str | None = Query(default=None, alias="status"),
    event_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    result = dispute_service.list_disputes(dispute_status, event_id, limit, offset)
    return PaginatedDisputeResponse(
        items=[DisputeResponse(**r) for r in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.get("/{dispute_id}", response_model=DisputeResponse)
def get_dispute(dispute_id: str, _: dict = _ANY_USER):
    row = dispute_service.get_dispute(dispute_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    return DisputeResponse(**row)


@router.patch("/{dispute_id}/status", response_model=DisputeResponse)
def update_dispute_status(dispute_id: str, body: DisputeStatusUpdate, _: dict = _ADMIN_REFEREE):
    body.validate_status()
    try:
        row = dispute_service.set_under_review(dispute_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    return DisputeResponse(**row)


@router.post("/{dispute_id}/resolve", response_model=DisputeResponse)
def resolve_dispute(
    dispute_id: str,
    body: DisputeResolveRequest,
    current_user: dict = _ADMIN_REFEREE,
):
    body.validate_resolution()
    try:
        row = dispute_service.resolve_dispute(dispute_id, body, current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    return DisputeResponse(**row)
