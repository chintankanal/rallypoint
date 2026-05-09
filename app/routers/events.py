from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user, require_roles
from app.services import event_service
from schemas.event import (
    AddAcademyToEvent,
    AssignRefereeRequest,
    AssignUmpireRequest,
    EventCreate,
    EventResponse,
    EventStatusUpdate,
    RefereeAssignmentResponse,
    UmpireAssignmentResponse,
)

router = APIRouter(prefix="/events", tags=["events"])

_ADMIN = Depends(require_roles("ADMIN"))
_ADMIN_COACH = Depends(require_roles("ADMIN", "COACH"))


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ("ADMIN", "COACH"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins and coaches only")
    try:
        row = event_service.create_event(body, current_user["role"], current_user.get("academy_id"), current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return EventResponse(**row)


@router.get("", tags=["events"])
def list_events(current_user: dict = Depends(get_current_user)):
    """List events — admin sees all, coach sees events for their academy."""
    return {"items": event_service.list_events(current_user["role"], current_user.get("academy_id"))}


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: str, _: dict = _ADMIN_COACH):
    row = event_service.get_event(event_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse(**row)


@router.post("/{event_id}/academies", response_model=EventResponse)
def add_academy_to_event(event_id: str, body: AddAcademyToEvent, _: dict = _ADMIN):
    row = event_service.add_academy_to_event(event_id, body.academy_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse(**row)


@router.patch("/{event_id}/status", response_model=EventResponse)
def update_event_status(event_id: str, body: EventStatusUpdate, _: dict = _ADMIN):
    try:
        row = event_service.update_event_status(event_id, body.status.value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.args[0])
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse(**row)


@router.post(
    "/{event_id}/referees",
    response_model=RefereeAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_referee(event_id: str, body: AssignRefereeRequest, _: dict = _ADMIN):
    row = event_service.assign_referee(event_id, body.user_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return RefereeAssignmentResponse(**row)


@router.post(
    "/{event_id}/umpires",
    response_model=UmpireAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_umpire(event_id: str, body: AssignUmpireRequest, _: dict = _ADMIN):
    row = event_service.assign_umpire(event_id, body.user_id, body.table_number)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return UmpireAssignmentResponse(**row)
