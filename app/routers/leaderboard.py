from fastapi import APIRouter, HTTPException, Query, status

from app.services import leaderboard_service
from schemas.leaderboard import (
    AgeGroupLeaderboardEntry,
    AgeGroupLeaderboardResponse,
    LeaderboardEntry,
    LeaderboardResponse,
)

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard", response_model=LeaderboardResponse)
def global_leaderboard(
    tier: str | None = Query(None, description="Filter by tier"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = leaderboard_service.global_leaderboard(tier, limit, offset)
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


@router.get("/analytics/leaderboard", response_model=AgeGroupLeaderboardResponse)
def age_group_leaderboard(
    age_group: str = Query(..., description="U10, U13, U15, or U17"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        result = leaderboard_service.age_group_leaderboard(age_group, limit, offset)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    items = [
        AgeGroupLeaderboardEntry(
            rank=r["rank"],
            player_id=r["player_id"],
            name=r["name"],
            current_rating=float(r["current_rating"]),
            tier=r["tier"],
            academy_name=r.get("academy_name"),
            age_jan1=r["age_jan1"],
            percentile=float(r["percentile"]),
            gender=r.get("gender"),
            age_group=r.get("age_grp"),
        )
        for r in result["items"]
    ]
    return AgeGroupLeaderboardResponse(
        age_group=result["age_group"], total=result["total"], items=items
    )
