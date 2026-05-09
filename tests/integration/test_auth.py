"""Integration tests for auth endpoints. Require TEST_DATABASE_URL."""
import uuid

import pytest


def _create_user(client, admin_token: str, role: str = "COACH", academy_id: str | None = None):
    payload = {
        "name": f"Test User {uuid.uuid4().hex[:6]}",
        "email": f"{uuid.uuid4().hex[:8]}@test.com",
        "role": role,
    }
    if academy_id:
        payload["academy_id"] = academy_id
    resp = client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return resp


@pytest.fixture(scope="module")
def admin_token(client):
    """Assumes an ADMIN user with email admin@test.com / changeme123 exists in test DB."""
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "changeme123"})
    if resp.status_code != 200:
        pytest.skip("Admin seed user not present in test DB")
    return resp.json()["access_token"]


def test_login_wrong_password(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nowhere.com", "password": "whatever"},
    )
    assert resp.status_code == 401


def test_no_token_returns_403(client):
    resp = client.get("/api/v1/users/some-id")
    assert resp.status_code in (401, 403)


def test_invalid_token_returns_401(client):
    resp = client.get(
        "/api/v1/users/some-id",
        headers={"Authorization": "Bearer thisisnotavalidtoken"},
    )
    assert resp.status_code == 401


def test_coach_without_academy_id_returns_422(client, admin_token):
    resp = _create_user(client, admin_token, role="COACH", academy_id=None)
    assert resp.status_code == 422


def test_wrong_role_returns_403(client, admin_token):
    """A COACH token should not be able to create users (ADMIN-only)."""
    # First create a COACH — we need an academy first
    # This test is best-effort; skip if no academy exists
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "coach@test.com", "password": "changeme123"},
    )
    if resp.status_code != 200:
        pytest.skip("Coach seed user not present in test DB")

    coach_token = resp.json()["access_token"]
    create_resp = client.post(
        "/api/v1/users",
        json={"name": "Attempt", "email": "x@x.com", "role": "PLAYER"},
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert create_resp.status_code == 403
