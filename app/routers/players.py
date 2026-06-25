import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.dependencies.auth import get_current_user, require_roles
from app.services import player_service
from schemas.player import (
    AcademyTransferRequest,
    AcademyTransferResponse,
    ClaimPlayerRequest,
    LinkAccountRequest,
    PlayerAcademyHistoryEntry,
    PlayerAcademyHistoryResponse,
    PlayerComputedStats,
    PlayerCreate,
    PlayerEventFixturesResponse,
    PlayerResponse,
    PlayerUpdate,
)
from schemas.rating import PaginatedRatingHistory, RatingHistoryEntry

router = APIRouter(prefix="/players", tags=["players"])

logger = structlog.get_logger()


def _send_player_claim_email(email: str, claim_code: str, player_name: str) -> None:
    if not settings.resend_api_key:
        logger.info("player_claim_email_skipped_no_api_key", email=email, claim_code=claim_code)
        return

    import httpx

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": "noreply@jlrs.app",
                "to": [email],
                "subject": "Your JLRS player claim code",
                "text": (
                    f"Your coach has created a JLRS player profile for {player_name}.\n"
                    f"Use this claim code to link the profile to your account: {claim_code}\n\n"
                    f"Visit {settings.frontend_url}/claim?code={claim_code} to claim your player profile. "
                    "If you do not have a JLRS account yet, register as a PLAYER first using this email, then claim the profile.\n\n"
                    "If you did not request this, you can ignore this email."
                ),
            },
            timeout=5.0,
        )
        if resp.status_code >= 400:
            logger.warning(
                "player_claim_email_send_failed",
                email=email,
                status_code=resp.status_code,
            )
        else:
            logger.info("player_claim_email_sent", email=email)
    except Exception as exc:
        logger.warning("player_claim_email_send_error", email=email, error=str(exc))


_ADMIN_COACH = Depends(require_roles("ADMIN", "COACH"))
_ANY_USER = Depends(get_current_user)


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
def create_player(body: PlayerCreate, current_user: dict = _ADMIN_COACH):
    row = player_service.create_player(body, current_user["user_id"])
    if row.get("contact_email") and row.get("claim_code"):
        # send email asynchronously via service; log result
        from app.services.email_service import send_claim_email

        try:
            send_claim_email(row["contact_email"], row["claim_code"], row["name"])
        except Exception:
            logger.exception("failed_to_send_claim_email", player_id=row.get("player_id"))
    return PlayerResponse(**row)


@router.get("", tags=["players"])
def list_all_players(_: dict = _ANY_USER):
    """All players ordered by academy name, then player name — used by event roster directory."""
    return {"items": player_service.list_all_players()}


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


@router.get("/{player_id}/fixtures", response_model=PlayerEventFixturesResponse)
def get_player_fixtures(player_id: str, _: dict = _ANY_USER):
    result = player_service.get_player_event_fixtures(player_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return PlayerEventFixturesResponse(**result)


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


@router.patch("/{player_id}", response_model=PlayerResponse)
def update_player(player_id: str, body: PlayerUpdate, current_user: dict = _ADMIN_COACH):
    try:
        row = player_service.update_player(
            player_id,
            body,
            current_user.get('academy_id'),
            current_user['role'],
            updated_by_id=current_user['user_id'],
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    return PlayerResponse(**row)


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


@router.post("/claim", response_model=PlayerResponse)
def claim_player(body: ClaimPlayerRequest, current_user: dict = Depends(require_roles("PLAYER"))):
    if current_user.get("player_id"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This account already has a linked player profile",
        )
    try:
        row = player_service.claim_player(current_user["user_id"], body.claim_code)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return PlayerResponse(**row)


@router.post("/{player_id}/send-claim-code")
def send_claim_code(player_id: str, _: dict = _ADMIN_COACH):
    """Trigger sending the claim-code email for a player (coach action)."""
    from app.services.email_service import send_claim_email

    row = player_service.get_player(player_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    if not row.get("contact_email"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No contact email for player")

    sent = send_claim_email(row["contact_email"], row.get("claim_code") or "", row["name"])
    if not sent:
        # Don't surface a 500 to the client for provider errors; return 202 with details logged.
        logger.warning("send_claim_code_failed", player_id=player_id, email=row.get("contact_email"))
        return {"detail": "Email not sent (provider error). Check server logs."}, 202
    return {"detail": "Email sent"}
