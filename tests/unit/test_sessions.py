"""Unit tests for session router behavior."""
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers.sessions import apply_session_ratings, generate_session_fixtures, mark_session_slot_unplayed
from schemas.session import MarkSlotUnplayedRequest


@pytest.fixture
def mock_conn(monkeypatch):
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    monkeypatch.setattr("app.routers.sessions.get_connection", lambda: mock_conn)
    return mock_cursor


def test_generate_session_fixtures_same_day_rotation_offset_uses_created_at(monkeypatch, mock_conn):
    session_row = {
        "session_id": "session-1",
        "event_id": "event-1",
        "session_date": date(2026, 6, 7),
        "created_at": datetime(2026, 6, 7, 9, 0, 0),
        "status": "SCHEDULED",
        "generated_at": None,
        "session_minutes": 90,
        "num_tables": 2,
        "match_format": "BEST_OF_3",
    }
    player_rows = [
        {
            "player_id": "player-1",
            "name": "Player 1",
            "current_rating": 1200,
            "rated_matches_completed": 0,
            "virtual_matches": 0,
        },
        {
            "player_id": "player-2",
            "name": "Player 2",
            "current_rating": 1200,
            "rated_matches_completed": 0,
            "virtual_matches": 0,
        },
    ]

    mock_conn.fetchall.side_effect = [player_rows, []]
    mock_conn.fetchone.side_effect = [
        session_row,
        {"offset": 1},
        {
            "slot_id": "slot-1",
            "round_number": 1,
            "wave_number": 1,
            "sub_round": None,
            "table_number": 1,
            "round_intent": "DISCOVERY",
            "gap_band": "A",
            "player_a_role": "A",
            "player_b_role": "B",
            "match_category": "DISCOVERY",
            "player_a_id": "player-1",
            "player_b_id": "player-2",
            "expected_rating_gap": 0.0,
            "status": "SCHEDULED",
            "match_id": None,
        },
    ]

    executed = []

    def record_execute(sql, params=None):
        executed.append((sql, params))

    mock_conn.execute.side_effect = record_execute

    monkeypatch.setattr("app.routers.sessions._load_config", lambda: {})
    monkeypatch.setattr("app.routers.sessions.get_tier", lambda rating, cfg: "UNSEEDED")

    def fake_generate_fixtures(**kwargs):
        assert kwargs["rotation_offset"] == 1
        return {
            "phase": "DISCOVERY",
            "spread": 0.0,
            "matches_per_player": 1,
            "regime": "DISCOVERY",
            "core_spread": 0.0,
            "provisional_count": 0,
            "present_player_count": 2,
            "competitive_max_gap": 0.0,
            "stretch_max_gap": 0.0,
            "slots": [
                {
                    "round_number": 1,
                    "wave_number": 1,
                    "sub_round": None,
                    "table_number": 1,
                    "round_intent": "DISCOVERY",
                    "gap_band": "A",
                    "player_a_role": "A",
                    "player_b_role": "B",
                    "match_category": "DISCOVERY",
                    "player_a_id": "player-1",
                    "player_b_id": "player-2",
                    "expected_rating_gap": 0.0,
                }
            ],
        }

    monkeypatch.setattr("app.services.fixture_engine.generate_fixtures", fake_generate_fixtures)

    from schemas.session import GenerateFixturesRequest

    request_body = GenerateFixturesRequest(player_ids=["player-1", "player-2"])
    response = generate_session_fixtures("session-1", request_body, current_user={"user_id": "user-1"})

    assert response.session_id == "session-1"
    assert any(
        "AND (s.session_date, s.created_at) < (%s, %s)" in sql for sql, _ in executed
    )
    assert any(params == ("event-1", session_row["session_date"], session_row["created_at"]) for _, params in executed)


def test_mark_session_slot_unplayed_sets_unplayed(monkeypatch, mock_conn):
    mock_conn.fetchone.side_effect = [
        {"session_id": "session-1"},
        {"status": "SCHEDULED", "match_id": None},
    ]
    response = mark_session_slot_unplayed(
        "session-1",
        "slot-1",
        MarkSlotUnplayedRequest(unplayed=True),
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert response == {"slot_id": "slot-1", "status": "UNPLAYED"}


def test_mark_session_slot_unplayed_undo(monkeypatch, mock_conn):
    mock_conn.fetchone.side_effect = [
        {"session_id": "session-1"},
        {"status": "UNPLAYED", "match_id": None},
    ]
    response = mark_session_slot_unplayed(
        "session-1",
        "slot-2",
        MarkSlotUnplayedRequest(unplayed=False),
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert response == {"slot_id": "slot-2", "status": "SCHEDULED"}


def test_mark_session_slot_unplayed_reject_played(monkeypatch, mock_conn):
    mock_conn.fetchone.side_effect = [
        {"session_id": "session-1"},
        {"status": "PLAYED", "match_id": None},
    ]
    with pytest.raises(HTTPException) as excinfo:
        mark_session_slot_unplayed(
            "session-1",
            "slot-3",
            MarkSlotUnplayedRequest(unplayed=True),
            current_user={"role": "ADMIN", "user_id": "user-1"},
        )

    assert excinfo.value.status_code == 409


def test_apply_session_ratings_ignores_unplayed_slots(monkeypatch, mock_conn):
    mock_conn.fetchone.side_effect = [
        {"session_id": "session-1", "scheduling_mode": "INTRA_ACADEMY"},
    ]
    mock_conn.fetchall.return_value = []
    monkeypatch.setattr("app.services.rating_engine.apply_ratings_batch", lambda conn, ids: [])

    result = apply_session_ratings(
        "session-1",
        current_user={"role": "ADMIN", "user_id": "user-1"},
    )

    assert result["matches_rated"] == 0
    assert result["already_up_to_date"] is True
