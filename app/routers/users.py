import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_connection
from app.dependencies.auth import require_roles
from app.services.auth_service import hash_password
from schemas.user import UserCreate, UserResponse, UserCreateResponse, UserListItem

router = APIRouter(prefix="/users", tags=["users"])

_ADMIN = Depends(require_roles("ADMIN"))


@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: dict = _ADMIN):
    if body.role.value == "COACH" and not body.academy_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="COACH role requires academy_id",
        )

    user_id = str(uuid.uuid4())
    temp_password = secrets.token_urlsafe(9)
    password_hash = hash_password(temp_password)

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

    return UserCreateResponse(**row, temporary_password=temp_password)


@router.get("", response_model=list[UserListItem])
def list_users(
    role: str | None = None,
    academy_id: str | None = None,
    _: dict = _ADMIN,
):
    query = """
        SELECT u.user_id, u.name, u.email, u.role, u.academy_id, u.is_active, u.created_at, a.name AS academy_name
        FROM users u
        LEFT JOIN academy a ON u.academy_id = a.academy_id
    """
    conditions = []
    params = []

    if role is not None:
        conditions.append("u.role = %s")
        params.append(role)
    if academy_id is not None:
        conditions.append("u.academy_id = %s")
        params.append(academy_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY u.created_at DESC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    return [UserListItem(**row) for row in rows]



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
