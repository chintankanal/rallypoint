"""Integration tests for session endpoints requiring a live test database."""
import uuid
from datetime import date

import pytest


def test_create_two_same_day_sessions_for_same_event(client, admin_token, test_db_conn):
    with test_db_conn.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE email = %s", ("admin@test.com",))
        row = cur.fetchone()
        if not row:
            pytest.skip("Admin seed user not present in test DB")
        admin_user_id = row["user_id"]

        event_id = str(uuid.uuid4())
        event_name = f"same-day-session-test-{uuid.uuid4().hex[:8]}"
        session_date = date.today()

        cur.execute(
            """
            INSERT INTO event (
                event_id, name, event_type, scheduling_mode,
                default_match_format, start_date, created_by, updated_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_id,
                event_name,
                "FRIENDLY",
                "INTRA_ACADEMY",
                "BEST_OF_3",
                session_date,
                admin_user_id,
                admin_user_id,
            ),
        )
        test_db_conn.commit()

    try:
        payload = {
            "session_date": session_date.isoformat(),
            "session_minutes": 90,
            "num_tables": 2,
        }

        resp1 = client.post(
            f"/api/v1/events/{event_id}/sessions",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp1.status_code == 201, resp1.text

        resp2 = client.post(
            f"/api/v1/events/{event_id}/sessions",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp2.status_code == 201, resp2.text

        assert resp1.json()["session_id"] != resp2.json()["session_id"]
        assert resp1.json()["session_date"] == resp2.json()["session_date"]
        assert resp1.json()["event_id"] == resp2.json()["event_id"]
    finally:
        with test_db_conn.cursor() as cur:
            cur.execute("DELETE FROM session WHERE event_id = %s", (event_id,))
            cur.execute("DELETE FROM event WHERE event_id = %s", (event_id,))
            test_db_conn.commit()
