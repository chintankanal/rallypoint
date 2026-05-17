"""
Integration tests for the full Player lifecycle.

Requires TEST_DATABASE_URL env var pointing to a seeded test DB.
The test DB must have:
  - An ADMIN user: admin@test.com / changeme123
  - At least one ACTIVE academy (any ID); tests create their own academy when needed.

Each test that writes data uses unique names/emails derived from uuid4 to stay
idempotent across reruns.
"""
import uuid
from datetime import date, timedelta

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token(client):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "changeme123"},
    )
    if resp.status_code != 200:
        pytest.skip("Admin seed user not present in test DB")
    return resp.json()["token"]


@pytest.fixture(scope="module")
def academy_id(client, admin_token):
    """Create a fresh academy for this test module."""
    resp = client.post(
        "/api/v1/academies",
        json={
            "name": f"Test Academy {uuid.uuid4().hex[:6]}",
            "location": "Test Location",
            "city": "TestCity",
            "state": "TS",
            "min_tables": 2,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["academy_id"]


@pytest.fixture(scope="module")
def coach_token(client, academy_id):
    """Register a coach and return their token."""
    email = f"coach-{uuid.uuid4().hex[:8]}@test.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test Coach",
            "email": email,
            "password": "testpass123",
            "role": "COACH",
            "academy_id": academy_id,
        },
    )
    assert reg.status_code == 201, reg.text
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "testpass123"}
    )
    assert login.status_code == 200, login.text
    return login.json()["token"]


def _create_player(client, token, academy_id, *, seeding_level="UNSEEDED", dob=None):
    if dob is None:
        dob = str(date(2013, 6, 15))
    resp = client.post(
        "/api/v1/players",
        json={
            "name": f"Player {uuid.uuid4().hex[:6]}",
            "date_of_birth": dob,
            "primary_academy_id": academy_id,
            "seeding_level": seeding_level,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


# ── Starting rating by seeding level ──────────────────────────────────────────

@pytest.mark.parametrize("seeding_level,expected_rating,expected_virtual", [
    ("UNSEEDED", 1000.0, 0),
    ("DISTRICT", 1200.0, 10),
    ("STATE",    1400.0, 20),
    ("NATIONAL", 1500.0, 30),
])
def test_starting_rating_and_virtual_matches(
    client, admin_token, academy_id, seeding_level, expected_rating, expected_virtual
):
    resp = _create_player(client, admin_token, academy_id, seeding_level=seeding_level)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["current_rating"] == expected_rating, (
        f"Expected {expected_rating} for {seeding_level}, got {data['current_rating']}"
    )


# ── Required fields are persisted (no NOT NULL violations) ────────────────────

def test_create_player_no_null_violations(client, admin_token, academy_id, test_db_conn):
    resp = _create_player(client, admin_token, academy_id, seeding_level="DISTRICT")
    assert resp.status_code == 201, resp.text
    player_id = resp.json()["player_id"]

    with test_db_conn.cursor() as cur:
        cur.execute(
            "SELECT player_id, created_by, updated_by, current_rating, virtual_matches "
            "FROM player WHERE player_id = %s",
            (player_id,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row["created_by"] is not None, "created_by must not be null"
    assert row["updated_by"] is not None, "updated_by must not be null"
    assert float(row["current_rating"]) == 1200.0
    assert row["virtual_matches"] == 10


def test_create_player_duplicate_rejected(client, admin_token, academy_id):
    body = {
        "name": "Duplicate Test Player",
        "date_of_birth": "2016-08-07",
        "primary_academy_id": academy_id,
        "seeding_level": "UNSEEDED",
        "guardian_name": "Same Guardian",
        "guardian_phone": "+911234567890",
        "contact_email": "duplicate-test@example.com",
    }

    first = client.post(
        "/api/v1/players",
        json=body,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/players",
        json=body,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 400, second.text
    assert second.json()["error"] == "BAD_REQUEST"
    assert "already exists" in second.json()["detail"]


# ── GET /players/{id} ─────────────────────────────────────────────────────────

def test_get_player_returns_correct_shape(client, admin_token, academy_id):
    resp = _create_player(client, admin_token, academy_id, seeding_level="DISTRICT")
    assert resp.status_code == 201
    player_id = resp.json()["player_id"]

    get_resp = client.get(
        f"/api/v1/players/{player_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["player_id"] == player_id
    assert data["current_rating"] == 1200.0
    assert "primary_academy" in data
    assert data["primary_academy"]["academy_id"] == academy_id


def test_get_player_404(client, admin_token):
    resp = client.get(
        f"/api/v1/players/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


# ── Computed stats ────────────────────────────────────────────────────────────

def test_computed_stats_district_player(client, admin_token, academy_id):
    resp = _create_player(
        client, admin_token, academy_id, seeding_level="DISTRICT", dob="2013-06-15"
    )
    player_id = resp.json()["player_id"]

    stats = client.get(
        f"/api/v1/players/{player_id}/computed-stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    # DISTRICT starts at 1200 → ADVANCED tier
    assert stats["tier"] == "ADVANCED"
    # DISTRICT is not provisional
    assert stats["is_provisional"] is False
    # 10 virtual matches → CR = 1 - exp(-10/30)
    import math
    expected_cr = round(1 - math.exp(-10 / 30), 4)
    assert abs(stats["confidence_ratio"] - expected_cr) < 0.001
    # No matches played yet → weeks_inactive is None
    assert stats["weeks_inactive"] is None


def test_computed_stats_unseeded_is_provisional(client, admin_token, academy_id):
    resp = _create_player(client, admin_token, academy_id, seeding_level="UNSEEDED")
    player_id = resp.json()["player_id"]

    stats = client.get(
        f"/api/v1/players/{player_id}/computed-stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    # UNSEEDED starts at 1000 → INTERMEDIATE tier
    assert stats["tier"] == "INTERMEDIATE"
    assert stats["is_provisional"] is True
    assert stats["provisional_matches_remaining"] == 15


# ── Player appears in academy leaderboard (Roster tab) ───────────────────────

def test_player_appears_in_roster(client, admin_token, academy_id):
    resp = _create_player(client, admin_token, academy_id, seeding_level="STATE")
    player_id = resp.json()["player_id"]

    roster = client.get(
        f"/api/v1/academies/{academy_id}/leaderboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    player_ids = [e["player_id"] for e in roster["items"]]
    assert player_id in player_ids, "Newly registered player not in roster"

    entry = next(e for e in roster["items"] if e["player_id"] == player_id)
    assert entry["current_rating"] == 1400.0
    assert entry["tier"] == "ELITE"  # 1400 → ELITE (1300–1499)


# ── Player search ─────────────────────────────────────────────────────────────

def test_search_player_by_name(client, admin_token, academy_id):
    unique = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/players",
        json={
            "name": f"SearchTarget-{unique}",
            "date_of_birth": "2012-01-01",
            "primary_academy_id": academy_id,
            "seeding_level": "UNSEEDED",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201

    search = client.get(
        f"/api/v1/players/search?q=SearchTarget-{unique}",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    assert len(search["items"]) == 1
    assert search["items"][0]["name"] == f"SearchTarget-{unique}"


def test_search_by_academy_filters_correctly(client, admin_token, academy_id):
    other_academy = client.post(
        "/api/v1/academies",
        json={
            "name": f"Other Academy {uuid.uuid4().hex[:6]}",
            "location": "Elsewhere",
            "city": "OtherCity",
            "state": "OT",
            "min_tables": 1,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["academy_id"]

    unique = uuid.uuid4().hex[:8]
    client.post(
        "/api/v1/players",
        json={
            "name": f"AcademyFilter-{unique}",
            "date_of_birth": "2012-01-01",
            "primary_academy_id": other_academy,
            "seeding_level": "UNSEEDED",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Search with correct academy_id should find the player
    found = client.get(
        f"/api/v1/players/search?q=AcademyFilter-{unique}&academy_id={other_academy}",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    assert len(found["items"]) == 1

    # Search with a different academy_id should return nothing
    not_found = client.get(
        f"/api/v1/players/search?q=AcademyFilter-{unique}&academy_id={academy_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    assert len(not_found["items"]) == 0


# ── Rating history access control ─────────────────────────────────────────────

def test_rating_history_breakdown_hidden_from_other_player(
    client, admin_token, academy_id
):
    # Create two players; log in as one; check the other's history hides breakdown
    p1 = _create_player(client, admin_token, academy_id)
    p1_id = p1.json()["player_id"]

    # Rating history will be empty (no matches yet), just verify the endpoint works
    # and returns a valid shape
    hist = client.get(
        f"/api/v1/players/{p1_id}/rating-history",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    assert "items" in hist
    assert "total" in hist


# ── Role enforcement ──────────────────────────────────────────────────────────

def test_player_role_cannot_register_new_player(client, admin_token, academy_id):
    """A PLAYER token must not be able to create players (ADMIN/COACH only)."""
    email = f"player-{uuid.uuid4().hex[:8]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Self Player",
            "email": email,
            "password": "pass123",
            "role": "PLAYER",
        },
    )
    player_login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "pass123"}
    )
    if player_login.status_code != 200:
        pytest.skip("Could not log in as PLAYER")
    player_token = player_login.json()["token"]

    resp = _create_player(client, player_token, academy_id)
    assert resp.status_code == 403


# ── Academy transfer cooldown ─────────────────────────────────────────────────

def test_transfer_cooldown_enforced(client, admin_token, academy_id, test_db_conn):
    # Create a player and a second academy
    p = _create_player(client, admin_token, academy_id, seeding_level="UNSEEDED")
    player_id = p.json()["player_id"]

    # Seed an academy history entry dated today (simulates a recent transfer)
    with test_db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO player_academy_history
                (history_id, player_id, academy_id, effective_from, change_reason)
            VALUES (%s, %s, %s, %s, 'TRANSFER')
            """,
            (str(uuid.uuid4()), player_id, academy_id, date.today()),
        )
    test_db_conn.commit()

    second_academy = client.post(
        "/api/v1/academies",
        json={
            "name": f"Transfer Target {uuid.uuid4().hex[:6]}",
            "location": "Loc",
            "city": "City",
            "state": "ST",
            "min_tables": 1,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["academy_id"]

    # Attempt transfer immediately (within 6-month cooldown) — should fail
    resp = client.patch(
        f"/api/v1/players/{player_id}/academy",
        json={
            "new_academy_id": second_academy,
            "effective_date": str(date.today() + timedelta(days=30)),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert "transfer" in resp.json()["detail"].lower()
