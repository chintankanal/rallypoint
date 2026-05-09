import psycopg2.errors
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.dependencies.auth import get_current_user, require_roles
from app.services import match_service
from schemas.match import ConfirmMatchRequest, MatchResponse, MatchSubmit, VoidMatchRequest

router = APIRouter(prefix="/matches", tags=["matches"])

_ANY_USER = Depends(get_current_user)
_ADMIN_REFEREE = Depends(require_roles("ADMIN", "REFEREE"))


@router.post("", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
def submit_match(body: MatchSubmit, current_user: dict = _ANY_USER):
    try:
        with get_connection() as conn:
            row = match_service.submit_match(
                conn, body, current_user["user_id"], caller_role=current_user["role"]
            )
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "MATCH_DUPLICATE", "message": "This match has already been submitted"},
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return MatchResponse(**row)


@router.get("/{match_id}", response_model=MatchResponse)
def get_match(match_id: str, _: dict = _ANY_USER):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT e.scheduling_mode FROM event e "
                "JOIN match m ON m.event_id = e.event_id "
                "WHERE m.match_id = %s",
                (match_id,),
            )
            ev = cur.fetchone()
            if not ev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
            row = match_service._fetch_match(cur, match_id, ev["scheduling_mode"])

    return MatchResponse(**row)


@router.post("/{match_id}/confirm", response_model=MatchResponse)
def confirm_match(match_id: str, body: ConfirmMatchRequest, current_user: dict = _ANY_USER):
    try:
        with get_connection() as conn:
            row = match_service.confirm_match(
                conn, match_id, body.confirmed, body.dispute_reason, current_user["user_id"]
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return MatchResponse(**row)


@router.post("/{match_id}/void", response_model=MatchResponse)
def void_match(match_id: str, body: VoidMatchRequest, current_user: dict = _ADMIN_REFEREE):
    from app.services.rating_engine import rollback_match

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ratings_applied_at FROM match WHERE match_id = %s",
                    (match_id,),
                )
                m = cur.fetchone()

            if m and m["ratings_applied_at"] is not None:
                rollback_match(conn, match_id)

            row = match_service.void_match(conn, match_id, body.void_reason, current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return MatchResponse(**row)
