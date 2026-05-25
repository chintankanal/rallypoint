import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import psycopg2.errors
import structlog
import structlog.contextvars
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import close_pool, init_pool
from app.rate_limit import limiter
from app.routers import (
    academies, analytics, auth, config, disputes, events,
    internal, leaderboard, matches, overview, players, seasons, sessions, users,
)

logger = structlog.get_logger()


# ── Middleware ─────────────────────────────────────────────────────────────────

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── App factory ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_pool(settings.database_url)
        logger.info("database_pool_initialised")
    except Exception as e:
        logger.error("database_pool_initialization_failed", error=str(e))
    yield
    close_pool()
    logger.info("database_pool_closed")


app = FastAPI(
    title="JLRS API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_PREFIX = "/api/v1"


def _normalize_origin(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    if port is None:
        return hostname
    if parsed.scheme == "http" and port == 80:
        return hostname
    if parsed.scheme == "https" and port == 443:
        return hostname
    return f"{hostname}:{port}"


def _should_redirect_to_frontend(request: Request) -> bool:
    request_origin = request.url.hostname.lower() if request.url.hostname else ""
    request_port = request.url.port
    if request_port and request_port not in (80, 443):
        request_origin = f"{request_origin}:{request_port}"
    frontend_origin = _normalize_origin(settings.frontend_url)
    return request_origin != frontend_origin


@app.get("/", include_in_schema=False)
def root(request: Request):
    """Redirect base URL to the frontend landing page."""
    if _should_redirect_to_frontend(request):
        return RedirectResponse(url=settings.frontend_url)
    return JSONResponse(
        content={"detail": "Frontend is not served from this backend host. Configure a separate frontend host or use /api/v1 endpoints."},
        status_code=status.HTTP_200_OK,
    )


@app.get("/overview", include_in_schema=False)
def overview_redirect(request: Request):
    """Redirect direct /overview browser requests to the frontend landing page."""
    if _should_redirect_to_frontend(request):
        return RedirectResponse(url=settings.frontend_url)
    return JSONResponse(
        content={"detail": "/overview is an API browser proxy and is not available on this backend host. Use the configured frontend host."},
        status_code=status.HTTP_200_OK,
    )


app.include_router(auth.router, prefix=_PREFIX)
app.include_router(users.router, prefix=_PREFIX)
app.include_router(academies.router, prefix=_PREFIX)
app.include_router(players.router, prefix=_PREFIX)
app.include_router(seasons.router, prefix=_PREFIX)
app.include_router(events.router, prefix=_PREFIX)
app.include_router(matches.router, prefix=_PREFIX)
app.include_router(disputes.router, prefix=_PREFIX)
app.include_router(sessions.router, prefix=_PREFIX)
app.include_router(leaderboard.router, prefix=_PREFIX)
app.include_router(overview.router, prefix=_PREFIX)
app.include_router(analytics.router, prefix=_PREFIX)
app.include_router(config.router, prefix=_PREFIX)
app.include_router(internal.router)


# ── Exception handlers ─────────────────────────────────────────────────────────

@app.exception_handler(psycopg2.errors.UniqueViolation)
async def unique_violation_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": "DUPLICATE", "detail": str(exc)},
    )


@app.exception_handler(psycopg2.errors.ForeignKeyViolation)
async def fk_violation_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "FOREIGN_KEY_VIOLATION", "detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "BAD_REQUEST", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "unknown")
    logger.exception("unhandled_error", path=str(request.url))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "request_id": request_id,
            "detail": "An unexpected error occurred",
        },
    )


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", tags=["health"])
def health():
    from app.database import get_connection
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "db": "unreachable"},
        )
