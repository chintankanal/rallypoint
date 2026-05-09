"""
Internal cron endpoints — protected by INTERNAL_JOB_SECRET header.
Called by Railway Crons; not listed in public API docs.
"""
import structlog
from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings

router = APIRouter(prefix="/internal", tags=["internal"])

logger = structlog.get_logger()


def _verify_secret(x_internal_secret: str | None) -> None:
    if x_internal_secret != settings.internal_job_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal job secret"
        )


@router.post("/jobs/daily")
def run_daily_job(x_internal_secret: str | None = Header(None)):
    _verify_secret(x_internal_secret)
    from app.jobs.daily_job import run
    try:
        result = run()
        logger.info("daily_job_completed", **result)
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.exception("daily_job_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Daily job failed: {exc}",
        )


@router.post("/jobs/weekly")
def run_weekly_job(x_internal_secret: str | None = Header(None)):
    _verify_secret(x_internal_secret)
    from app.jobs.weekly_job import run
    try:
        result = run()
        logger.info("weekly_job_completed", **result)
        return {"status": "ok", "result": result}
    except Exception as exc:
        logger.exception("weekly_job_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Weekly job failed: {exc}",
        )
