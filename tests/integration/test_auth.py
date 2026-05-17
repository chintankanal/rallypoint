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
    return resp.json()["token"]


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


def test_public_register_non_player_role_returns_400(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Not Allowed", "email": "notallowed@test.com", "password": "securepass", "role": "COACH"},
    )
    assert resp.status_code == 400


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

    coach_token = resp.json()["token"]
    create_resp = client.post(
        "/api/v1/users",
        json={"name": "Attempt", "email": "x@x.com", "role": "PLAYER"},
        headers={"Authorization": f"Bearer {coach_token}"},
    )
    assert create_resp.status_code == 403


def test_player_claims_existing_player_with_code(client, admin_token, test_db_conn):
    import uuid

    player_email = f"player-{uuid.uuid4().hex[:8]}@test.com"
    player_data = {
        "name": "Claimable Player",
        "date_of_birth": "2010-01-01",
        "gender": "MALE",
        "primary_academy_id": None,
        "seeding_level": "UNSEEDED",
        "nationality": "India",
    }

    # create an academy if none exists
    academy_resp = client.get("/api/v1/academies?status=ACTIVE")
    if academy_resp.status_code != 200 or not academy_resp.json().get("items"):
        pytest.skip("No academy available for player creation")
    academy_id = academy_resp.json()["items"][0]["academy_id"]
    player_data["primary_academy_id"] = academy_id

    create_resp = client.post(
        "/api/v1/players",
        json=player_data,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["claim_code"]
    assert not created["is_claimed"]

    # register a new player user, then login and claim the player
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"name": "New Player", "email": player_email, "password": "securepass", "role": "PLAYER"},
    )
    assert register_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": player_email, "password": "securepass"},
    )
    assert login_resp.status_code == 200
    user_json = login_resp.json()
    user_token = user_json["token"]
    user_id = user_json["user_id"]

    claim_resp = client.post(
        "/api/v1/players/claim",
        json={"claim_code": created["claim_code"]},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert claim_resp.status_code == 200
    claimed = claim_resp.json()
    assert claimed["player_id"] == created["player_id"]
    assert claimed["is_claimed"] is True
    assert claimed["primary_academy"]["academy_id"] == academy_id

    with test_db_conn.cursor() as cur:
        cur.execute("SELECT user_id FROM player WHERE player_id = %s", (created["player_id"],))
        row = cur.fetchone()
        assert row and row["user_id"] is not None
        cur.execute("SELECT academy_id FROM users WHERE user_id = %s", (user_id,))
        user_row = cur.fetchone()
        assert user_row and user_row["academy_id"] == academy_id


def test_admin_links_player_account_updates_user_academy(client, admin_token, test_db_conn):
    import uuid

    # create an academy if none exists
    academy_resp = client.get("/api/v1/academies?status=ACTIVE")
    if academy_resp.status_code != 200 or not academy_resp.json().get("items"):
        pytest.skip("No academy available for player creation")
    academy_id = academy_resp.json()["items"][0]["academy_id"]

    player_data = {
        "name": f"Linked Player {uuid.uuid4().hex[:6]}",
        "date_of_birth": "2010-05-01",
        "gender": "MALE",
        "primary_academy_id": academy_id,
        "seeding_level": "UNSEEDED",
        "nationality": "India",
    }

    create_resp = client.post(
        "/api/v1/players",
        json=player_data,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert not created["is_claimed"]

    player_email = f"linked-{uuid.uuid4().hex[:8]}@test.com"
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Link Player", "email": player_email, "password": "securepass", "role": "PLAYER"},
    )
    assert register_resp.status_code == 201
    user_id = register_resp.json()["user_id"]

    link_resp = client.patch(
        f"/api/v1/players/{created['player_id']}/link-account",
        json={"user_id": user_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert link_resp.status_code == 200
    linked = link_resp.json()
    assert linked["is_claimed"] is True

    with test_db_conn.cursor() as cur:
        cur.execute("SELECT academy_id FROM users WHERE user_id = %s", (user_id,))
        user_row = cur.fetchone()
        assert user_row and user_row["academy_id"] == academy_id
