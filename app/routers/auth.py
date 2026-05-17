import structlog
from fastapi import APIRouter, HTTPException, Request, status

from app.database import get_connection
from app.rate_limit import limiter
from app.services.auth_service import (
    consume_otp,
    create_token,
    generate_otp_code,
    hash_password,
    store_otp,
    verify_password,
)
from schemas.auth import LoginRequest, OTPRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

logger = structlog.get_logger()


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest):
    if not body.password and not body.otp_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either password or otp_code",
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT u.user_id, u.role, u.academy_id, a.name AS academy_name, u.password_hash, u.is_active, p.player_id "
                "FROM users u "
                "LEFT JOIN academy a ON a.academy_id = u.academy_id "
                "LEFT JOIN player p ON p.user_id = u.user_id "
                "WHERE u.email = %s",
                (body.email,),
            )
            user = cur.fetchone()

            if not user or not user["is_active"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )

            if body.otp_code:
                if not consume_otp(cur, str(user["user_id"]), body.otp_code):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="OTP code is invalid or expired",
                    )
            else:
                if not verify_password(body.password, user["password_hash"]):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials",
                    )

    token, expires_at = create_token(
        str(user["user_id"]), user["role"], str(user["academy_id"]) if user["academy_id"] else None
    )
    return TokenResponse(
        token=token,
        user_id=str(user["user_id"]),
        role=user["role"],
        academy_id=str(user["academy_id"]) if user["academy_id"] else None,
        academy_name=user["academy_name"],
        player_id=str(user["player_id"]) if user["player_id"] else None,
        expires_at=expires_at,
    )


@router.post("/request-otp", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
def request_otp(request: Request, body: OTPRequest):
    from app.config import settings

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, email, is_active FROM users WHERE email = %s",
                (body.email,),
            )
            user = cur.fetchone()

            # Always return 202 to avoid email enumeration
            if not user or not user["is_active"]:
                return {"detail": "If that email is registered, a code has been sent"}

            code = generate_otp_code()
            store_otp(cur, str(user["user_id"]), code)

    _send_otp_email(body.email, code, settings.resend_api_key)
    return {"detail": "If that email is registered, a code has been sent"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    import uuid
    if body.role != "PLAYER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public registration only supports PLAYER accounts",
        )

    user_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, name, email, phone, role, gender, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING user_id, name, email, role, academy_id, is_active
                """,
                (
                    user_id,
                    body.name,
                    body.email,
                    body.phone,
                    "PLAYER",
                    body.gender,
                    hash_password(body.password),
                ),
            )
            row = cur.fetchone()

    return {"user_id": row["user_id"], "name": row["name"], "email": row["email"],
            "role": row["role"], "academy_id": row["academy_id"]}


def _send_otp_email(email: str, code: str, api_key: str) -> None:
    if not api_key:
        logger.info("otp_email_skipped_no_api_key", email=email, code=code)
        return
    import httpx
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": "noreply@jlrs.app",
                "to": [email],
                "subject": "Your JLRS login code",
                "text": (
                    f"Your JLRS login code is: {code}\n"
                    "This code expires in 10 minutes.\n"
                    "If you did not request this, ignore this email."
                ),
            },
            timeout=5.0,
        )
        if resp.status_code >= 400:
            logger.warning("otp_email_send_failed", email=email, status_code=resp.status_code)
        else:
            logger.info("otp_email_sent", email=email)
    except Exception as exc:
        logger.warning("otp_email_send_error", email=email, error=str(exc))
