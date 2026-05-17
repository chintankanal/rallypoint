from fastapi import APIRouter

from app.database import get_connection
from schemas.leaderboard import OverviewResponse

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=OverviewResponse)
def get_overview():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM player")
            total_players = int(cur.fetchone()["count"])

            cur.execute("SELECT COUNT(*) AS count FROM match WHERE ratings_applied_at IS NOT NULL")
            matches_processed = int(cur.fetchone()["count"])

            cur.execute("SELECT COUNT(*) AS count FROM academy WHERE status = 'ACTIVE'")
            participating_academies = int(cur.fetchone()["count"])

    return OverviewResponse(
        total_players=total_players,
        matches_processed=matches_processed,
        participating_academies=participating_academies,
    )
