"""Unit tests for match router apply ratings behavior."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers.matches import apply_event_matches_ratings


@pytest.fixture
def mock_cursor(monkeypatch):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    monkeypatch.setattr("app.routers.matches.get_connection", lambda: mock_conn)
    return mock_cursor


def test_apply_event_matches_ratings_rejects_inter_academy(monkeypatch, mock_cursor):
    mock_cursor.fetchone.return_value = {"scheduling_mode": "INTER_ACADEMY"}

    with pytest.raises(HTTPException) as excinfo:
        apply_event_matches_ratings(
            "event-1",
            current_user={"role": "ADMIN", "user_id": "user-1"},
        )

    assert excinfo.value.status_code == 400
    assert "league apply-ratings" in str(excinfo.value.detail).lower()


def test_apply_event_matches_ratings_applies_pending_and_confirmed_matches(monkeypatch, mock_cursor):
    mock_cursor.fetchone.side_effect = [
        {"scheduling_mode": "INTRA_ACADEMY"},
    ]
    mock_cursor.fetchall.side_effect = [
        [{"match_id": "match-1"}, {"match_id": "match-2"}],
        [{"match_id": "match-1"}, {"match_id": "match-2"}],
    ]

    captured = []
    monkeypatch.setattr("app.services.rating_engine.apply_ratings_batch", lambda conn, ids: captured.extend(ids) or [{"player_id": "p1", "tier_before": "INTERMEDIATE", "tier_after": "ADVANCED"}])
    monkeypatch.setattr("app.services.webhook_service.fire", lambda event, payload: None)

    result = apply_event_matches_ratings(
        "event-1",
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert result["event_id"] == "event-1"
    assert result["matches_rated"] == 2
    assert result["matches_auto_confirmed"] == 2
    assert result["already_up_to_date"] is False
    assert captured == ["match-1", "match-2"]
    assert result["tier_changes"][0]["player_id"] == "p1"


def test_apply_event_matches_ratings_idempotent_when_no_new_matches(monkeypatch, mock_cursor):
    mock_cursor.fetchone.return_value = {"scheduling_mode": "INTRA_ACADEMY"}
    mock_cursor.fetchall.return_value = []
    monkeypatch.setattr("app.services.rating_engine.apply_ratings_batch", lambda conn, ids: [])
    monkeypatch.setattr("app.services.webhook_service.fire", lambda event, payload: None)

    result = apply_event_matches_ratings(
        "event-1",
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert result["matches_rated"] == 0
    assert result["already_up_to_date"] is True
    assert result["matches_auto_confirmed"] == 0
