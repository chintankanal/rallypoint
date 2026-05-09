import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.dependencies.auth import require_roles
from app.services.auth_service import hash_password
from schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])

_ADMIN = Depends(require_roles("ADMIN"))


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: dict = _ADMIN):
    if body.role.value == "COACH" and not body.academy_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="COACH role requires academy_id",
        )

    user_id = str(uuid.uuid4())
    password_hash = hash_password("changeme123")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, name, email, phone, role, academy_id, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING user_id, name, email, role, academy_id, is_active, created_at
                """,
                (
                    user_id,
                    body.name,
                    body.email,
                    body.phone,
                    body.role.value,
                    body.academy_id,
                    password_hash,
                ),
            )
            row = cur.fetchone()

    return UserResponse(**row)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, _: dict = _ADMIN):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id, name, email, role, academy_id, is_active, created_at "
                "FROM users WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(**row)
