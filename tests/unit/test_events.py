"""Unit tests for event router mark-unplayed and apply-ratings behavior."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers.events import apply_event_ratings, mark_event_slot_unplayed
from schemas.event import MarkSlotUnplayedRequest


@pytest.fixture
def mock_cursor(monkeypatch):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    monkeypatch.setattr("app.routers.events.get_connection", lambda: mock_conn)
    return mock_cursor


def test_mark_event_slot_unplayed_sets_status(monkeypatch, mock_cursor):
    mock_cursor.fetchone.side_effect = [
        {"fixture_state": "FIXTURE_FROZEN", "host_academy_id": "host-1"},
        {"status": "SCHEDULED", "match_id": None},
    ]
    executed = []

    def record_execute(sql, params=None):
        executed.append((sql, params))

    mock_cursor.execute.side_effect = record_execute

    response = mark_event_slot_unplayed(
        "event-1",
        "slot-1",
        MarkSlotUnplayedRequest(unplayed=True),
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert response == {"slot_id": "slot-1", "status": "UNPLAYED"}
    assert any("UPDATE event_fixture_slot SET status = %s" in sql for sql, _ in executed)
    assert any(params == ("UNPLAYED", "slot-1", "event-1") for _, params in executed)


def test_mark_event_slot_unplayed_undo(monkeypatch, mock_cursor):
    mock_cursor.fetchone.side_effect = [
        {"fixture_state": "FIXTURE_FROZEN", "host_academy_id": "host-1"},
        {"status": "UNPLAYED", "match_id": None},
    ]
    response = mark_event_slot_unplayed(
        "event-1",
        "slot-2",
        MarkSlotUnplayedRequest(unplayed=False),
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert response == {"slot_id": "slot-2", "status": "SCHEDULED"}


def test_mark_event_slot_unplayed_reject_played(monkeypatch, mock_cursor):
    mock_cursor.fetchone.side_effect = [
        {"fixture_state": "FIXTURE_FROZEN", "host_academy_id": "host-1"},
        {"status": "PLAYED", "match_id": None},
    ]

    with pytest.raises(HTTPException) as excinfo:
        mark_event_slot_unplayed(
            "event-1",
            "slot-3",
            MarkSlotUnplayedRequest(unplayed=True),
            current_user={"role": "ADMIN", "user_id": "user-1"},
        )

    assert excinfo.value.status_code == 409
    assert "played slot" in excinfo.value.detail.lower()


def test_apply_event_ratings_passes_when_unplayed_slots_resolved(monkeypatch, mock_cursor):
    mock_cursor.fetchone.side_effect = [
        {"fixture_state": "FIXTURE_FROZEN", "scheduling_mode": "INTER_ACADEMY", "event_type": "LEAGUE"},
        {"cnt": 0},
    ]
    mock_cursor.fetchall.return_value = []
    monkeypatch.setattr("app.routers.events.apply_ratings_batch", lambda conn, ids: [])

    result = apply_event_ratings(
        "event-1",
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert result["fixture_state"] == "RATINGS_APPLIED"
    assert result["matches_processed"] == 0
