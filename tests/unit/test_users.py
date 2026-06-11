import uuid
import pytest


@pytest.fixture(scope="module")
def admin_token(client):
    """Assumes an ADMIN user with email admin@test.com / changeme123 exists in test DB."""
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "changeme123"})
    if resp.status_code != 200:
        pytest.skip("Admin seed user not present in test DB")
    return resp.json()["token"]




@pytest.fixture(scope="module")
def test_academy_id(client, admin_token):
    # Try to find an active academy first
    resp = client.get("/api/v1/academies?status=ACTIVE")
    if resp.status_code == 200 and resp.json().get("items"):
        return resp.json()["items"][0]["academy_id"]

    # Otherwise create one
    payload = {
        "name": f"Test Academy {uuid.uuid4().hex[:6]}",
        "location": "123 Test St",
        "city": "Test City",
        "state": "Test State",
        "min_tables": 4,
    }
    resp = client.post(
        "/api/v1/academies",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["academy_id"]


def test_create_coach_success(client, admin_token, test_academy_id):
    email = f"coach-{uuid.uuid4().hex[:8]}@test.com"
    phone = f"+919{uuid.uuid4().hex[:9]}"
    payload = {
        "name": "Test Coach",
        "email": email,
        "role": "COACH",
        "academy_id": test_academy_id,
        "phone": phone,
    }
    resp = client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == email
    assert data["role"] == "COACH"
    assert data["academy_id"] == test_academy_id
    assert "temporary_password" in data
    assert len(data["temporary_password"]) > 0


def test_create_coach_without_academy_id_fails(client, admin_token):
    email = f"coach-{uuid.uuid4().hex[:8]}@test.com"
    phone = f"+919{uuid.uuid4().hex[:9]}"
    payload = {
        "name": "Test Coach No Academy",
        "email": email,
        "role": "COACH",
        "phone": phone,
    }
    resp = client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert "COACH role requires academy_id" in resp.json()["detail"]


def test_list_users_filters(client, admin_token, test_academy_id):
    # Ensure there's at least one coach
    email = f"coach-{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/users",
        json={
            "name": "Another Coach",
            "email": email,
            "role": "COACH",
            "academy_id": test_academy_id,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # List all users
    resp = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 1
    # Check that academy_name exists in keys and password is NOT exposed
    for u in users:
        assert "academy_name" in u
        assert "password_hash" not in u
        assert "temporary_password" not in u

    # List users filtered by COACH role
    resp = client.get(
        "/api/v1/users?role=COACH",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    coaches = resp.json()
    assert len(coaches) >= 1
    for c in coaches:
        assert c["role"] == "COACH"
        assert c["academy_id"] == test_academy_id
        assert c["academy_name"] is not None

    # List users filtered by academy_id
    resp = client.get(
        f"/api/v1/users?academy_id={test_academy_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    academy_users = resp.json()
    assert len(academy_users) >= 1
    for u in academy_users:
        assert u["academy_id"] == test_academy_id
