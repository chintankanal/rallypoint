import hashlib
import hmac
import secrets
import string
from datetime import datetime, timezone, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
OTP_EXPIRY_MINUTES = 10


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user_id: str, role: str, academy_id: str | None) -> tuple[str, datetime]:
    """Return (jwt_string, expires_at)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    payload = {
        "sub": user_id,
        "role": role,
        "academy_id": academy_id,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, expire


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


# ── OTP ───────────────────────────────────────────────────────────────────────

def generate_otp_code() -> str:
    """Return a cryptographically adequate random 6-digit string."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def hash_otp_code(code: str) -> str:
    """
    HMAC-SHA256 with a random 32-hex-char salt; returns 'salt:hex_digest'.
    Avoids passlib/bcrypt for short-lived codes — stdlib only, timing-safe.
    """
    salt = secrets.token_hex(16)
    digest = hmac.new(salt.encode(), code.encode(), hashlib.sha256).hexdigest()
    return f"{salt}:{digest}"


def verify_otp_code(code: str, stored: str) -> bool:
    try:
        salt, digest = stored.split(":", 1)
    except ValueError:
        return False
    expected = hmac.new(salt.encode(), code.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def store_otp(cur, user_id: str, code: str) -> None:
    """Delete any existing OTP for the user and insert a fresh one."""
    import uuid
    cur.execute("DELETE FROM otp_code WHERE user_id = %s", (user_id,))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    cur.execute(
        """
        INSERT INTO otp_code (otp_id, user_id, code_hash, expires_at)
        VALUES (%s, %s, %s, %s)
        """,
        (str(uuid.uuid4()), user_id, hash_otp_code(code), expires_at),
    )


def consume_otp(cur, user_id: str, code: str) -> bool:
    """
    Verify and delete the OTP for user_id.
    Returns True on success, False on wrong/expired/missing code.
    """
    cur.execute(
        """
        SELECT otp_id, code_hash, expires_at
        FROM otp_code
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if not row:
        return False
    if datetime.now(timezone.utc) > row["expires_at"].replace(tzinfo=timezone.utc):
        cur.execute("DELETE FROM otp_code WHERE user_id = %s", (user_id,))
        return False
    if not verify_otp_code(code, row["code_hash"]):
        return False
    cur.execute("DELETE FROM otp_code WHERE otp_id = %s", (row["otp_id"],))
    return True
