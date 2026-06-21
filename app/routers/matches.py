import psycopg2.errors
from typing import List
from uuid import UUID
from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.database import get_connection
from app.dependencies.auth import get_current_user, require_roles
from app.services import match_service
from schemas.match import (
    ConfirmMatchRequest,
    MatchDeleteRequest,
    MatchResponse,
    MatchSubmit,
    MatchUpdate,
    VoidMatchRequest,
)

router = APIRouter(prefix="/matches", tags=["matches"])

_ANY_USER = Depends(get_current_user)
_ADMIN_REFEREE = Depends(require_roles("ADMIN", "REFEREE"))
_ADMIN_COACH = Depends(require_roles("ADMIN", "COACH"))


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


@router.get("/pending", response_model=List[MatchResponse])
def list_pending_matches(current_user: dict = _ANY_USER):
    if current_user["role"] != "PLAYER" or not current_user.get("player_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only PLAYER accounts with a linked player profile can view pending matches",
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT m.match_id, e.scheduling_mode "
                "FROM match m JOIN event e ON e.event_id = m.event_id "
                "WHERE m.confirmation_status = 'PENDING' "
                "AND (m.player_a_id = %s OR m.player_b_id = %s) "
                "ORDER BY m.match_date DESC, m.match_timestamp DESC",
                (current_user["player_id"], current_user["player_id"]),
            )
            rows = cur.fetchall()
            matches = [
                MatchResponse(**match_service._fetch_match(cur, row["match_id"], row["scheduling_mode"]))
                for row in rows
            ]
    return matches


@router.get("/{match_id}", response_model=MatchResponse)
def get_match(match_id: UUID, _: dict = _ANY_USER):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT e.scheduling_mode FROM event e "
                "JOIN match m ON m.event_id = e.event_id "
                "WHERE m.match_id = %s",
                (str(match_id),),
            )
            ev = cur.fetchone()
            if not ev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
            row = match_service._fetch_match(cur, str(match_id), ev["scheduling_mode"])

    return MatchResponse(**row)


@router.get("/session/{session_id}", response_model=List[MatchResponse])
def list_session_matches(session_id: str, current_user: dict = _ADMIN_COACH):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT m.match_id, e.scheduling_mode "
                "FROM match m JOIN event e ON e.event_id = m.event_id "
                "WHERE m.session_id = %s "
                "ORDER BY m.match_date DESC, m.match_timestamp DESC",
                (session_id,),
            )
            rows = cur.fetchall()
            matches = [
                MatchResponse(**match_service._fetch_match(cur, row["match_id"], row["scheduling_mode"]))
                for row in rows
            ]

    return matches


@router.get("/event/{event_id}", response_model=List[MatchResponse])
def list_event_matches(event_id: str, current_user: dict = _ADMIN_COACH):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT m.match_id, e.scheduling_mode "
                "FROM match m JOIN event e ON e.event_id = m.event_id "
                "WHERE m.event_id = %s "
                "ORDER BY m.match_date DESC, m.match_timestamp DESC",
                (event_id,),
            )
            rows = cur.fetchall()
            matches = [
                MatchResponse(**match_service._fetch_match(cur, row["match_id"], row["scheduling_mode"]))
                for row in rows
            ]

    return matches


@router.post("/event/{event_id}/apply-ratings")
def apply_event_matches_ratings(event_id: str, current_user: dict = _ADMIN_COACH):
    from app.services.rating_engine import apply_ratings_batch
    from app.services.webhook_service import fire

    user_id = current_user["user_id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT scheduling_mode FROM event WHERE event_id = %s",
                (event_id,),
            )
            ev = cur.fetchone()
            if not ev:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
            if ev["scheduling_mode"] != "INTRA_ACADEMY":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Use the league apply-ratings flow for inter-academy events",
                )

        match_ids, auto_confirmed_count = match_service.auto_confirm_event_matches(conn, event_id)

        if not match_ids:
            return {
                "event_id": event_id,
                "matches_rated": 0,
                "matches_auto_confirmed": auto_confirmed_count,
                "tier_changes": [],
                "already_up_to_date": True,
            }

        tier_changes = apply_ratings_batch(conn, match_ids)

    for tc in tier_changes:
        fire("player.tier_changed", tc)

    return {
        "event_id": event_id,
        "matches_rated": len(match_ids),
        "matches_auto_confirmed": auto_confirmed_count,
        "tier_changes": tier_changes,
        "already_up_to_date": False,
    }


@router.post("/{match_id}/confirm", response_model=MatchResponse)
def confirm_match(match_id: UUID, body: ConfirmMatchRequest, current_user: dict = _ANY_USER):
    if current_user["role"] == "PLAYER" and not current_user.get("player_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PLAYER accounts must have a linked player profile to confirm match results",
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT player_a_id, player_b_id FROM match WHERE match_id = %s",
                (str(match_id),),
            )
            match = cur.fetchone()
            if not match:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
            if current_user["role"] == "PLAYER" and current_user["player_id"] not in (
                match["player_a_id"], match["player_b_id"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You may only confirm or dispute matches you participated in",
                )

        try:
            row = match_service.confirm_match(
                conn, str(match_id), body.confirmed, body.dispute_reason, current_user["user_id"]
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return MatchResponse(**row)


@router.patch("/{match_id}", response_model=MatchResponse)
def update_match(match_id: UUID, body: MatchUpdate, current_user: dict = _ADMIN_COACH):
    try:
        with get_connection() as conn:
            row = match_service.update_match(conn, str(match_id), body, current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return MatchResponse(**row)


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_match(match_id: UUID, body: MatchDeleteRequest | None = Body(default=None), current_user: dict = _ADMIN_COACH):
    try:
        with get_connection() as conn:
            match_service.delete_match(conn, str(match_id), current_user["user_id"], body.reason if body else None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{match_id}/void", response_model=MatchResponse)
def void_match(match_id: UUID, body: VoidMatchRequest, current_user: dict = _ADMIN_REFEREE):
    from app.services.rating_engine import rollback_match

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ratings_applied_at FROM match WHERE match_id = %s",
                    (str(match_id),),
                )
                m = cur.fetchone()

            if m and m["ratings_applied_at"] is not None:
                rollback_match(conn, match_id)

            row = match_service.void_match(conn, match_id, body.void_reason, current_user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return MatchResponse(**row)
