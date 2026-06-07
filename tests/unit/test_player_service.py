"""Unit tests for player_service logic that requires no DB connection."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from app.services.player_service import _SEEDING_DEFAULTS, get_computed_stats


# ── Seeding defaults ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("level,expected_rating,expected_virtual", [
    ("UNSEEDED", 1000.0, 0),
    ("DISTRICT", 1200.0, 10),
    ("STATE",    1400.0, 20),
    ("NATIONAL", 1500.0, 30),
])
def test_seeding_defaults(level, expected_rating, expected_virtual):
    rating, virtual = _SEEDING_DEFAULTS[level]
    assert rating == expected_rating
    assert virtual == expected_virtual


# ── get_computed_stats (mocking DB) ───────────────────────────────────────────

def _mock_row(
    *,
    current_rating=1200,
    rated_matches_completed=5,
    virtual_matches=10,
    seeding_level="DISTRICT",
    date_of_birth=date(2013, 6, 15),
    last_match_date=None,
):
    return {
        "player_id": "test-id",
        "current_rating": current_rating,
        "rated_matches_completed": rated_matches_completed,
        "virtual_matches": virtual_matches,
        "seeding_level": seeding_level,
        "date_of_birth": date_of_birth,
        "last_match_date": last_match_date,
    }


def _mock_role_exposure_row():
    """Mock row returned by _get_player_role_exposure SQL query."""
    return {
        "as_peer": 5,
        "as_anchoring": 2,
        "as_stretching": 3,
        "bye_count": 1,
    }


@pytest.fixture
def mock_conn(monkeypatch):
    """Patch get_connection to yield a fake connection with configurable fetchone."""
    mock_cur = MagicMock()
    mock_conn_obj = MagicMock()
    mock_conn_obj.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn_obj.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_conn_obj)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr("app.services.player_service.get_connection", lambda: mock_ctx)
    return mock_cur


def test_computed_stats_not_found(mock_conn):
    mock_conn.fetchone.side_effect = [None]
    assert get_computed_stats("nonexistent") is None


def test_computed_stats_tier_from_rating(mock_conn):
    mock_conn.fetchone.side_effect = [_mock_row(current_rating=1350), _mock_role_exposure_row()]
    stats = get_computed_stats("p1")
    assert stats["tier"] == "ELITE"


def test_computed_stats_provisional_unseeded_under_15(mock_conn):
    mock_conn.fetchone.side_effect = [
        _mock_row(seeding_level="UNSEEDED", rated_matches_completed=5, virtual_matches=5),
        _mock_role_exposure_row(),
    ]
    stats = get_computed_stats("p1")
    assert stats["is_provisional"] is True
    assert stats["provisional_matches_remaining"] == 5


def test_computed_stats_provisional_clears_at_15(mock_conn):
    mock_conn.fetchone.side_effect = [
        _mock_row(seeding_level="UNSEEDED", rated_matches_completed=10, virtual_matches=5),
        _mock_role_exposure_row(),
    ]
    stats = get_computed_stats("p1")
    assert stats["is_provisional"] is False
    assert stats["provisional_matches_remaining"] == 0


def test_computed_stats_district_not_provisional(mock_conn):
    # DISTRICT players are never provisional regardless of match count
    mock_conn.fetchone.side_effect = [
        _mock_row(seeding_level="DISTRICT", rated_matches_completed=0, virtual_matches=10),
        _mock_role_exposure_row(),
    ]
    stats = get_computed_stats("p1")
    assert stats["is_provisional"] is False


def test_computed_stats_weeks_inactive_when_no_last_match(mock_conn):
    mock_conn.fetchone.side_effect = [_mock_row(last_match_date=None), _mock_role_exposure_row()]
    stats = get_computed_stats("p1")
    assert stats["weeks_inactive"] is None
    assert stats["inactivity_decay_active"] is False


@pytest.mark.parametrize("days_ago,expected_inactive", [
    (55, False),   # 55 days < 8 weeks (56 days)
    (56, True),    # exactly 8 weeks — boundary is >=
    (100, True),
])
def test_computed_stats_inactivity_decay(monkeypatch, mock_conn, days_ago, expected_inactive):
    from datetime import timedelta
    today = date(2026, 4, 28)
    monkeypatch.setattr("app.services.player_service.date", type("_D", (), {"today": staticmethod(lambda: today)})())
    mock_conn.fetchone.side_effect = [
        _mock_row(last_match_date=today - timedelta(days=days_ago)),
        _mock_role_exposure_row(),
    ]
    stats = get_computed_stats("p1")
    assert stats["inactivity_decay_active"] is expected_inactive


@pytest.mark.parametrize("total,expected_tier", [
    (14, True),
    (15, False),
])
def test_computed_stats_provisional_boundary_exact(mock_conn, total, expected_tier):
    rm = max(0, total - 0)
    mock_conn.fetchone.side_effect = [
        _mock_row(seeding_level="UNSEEDED", rated_matches_completed=rm, virtual_matches=0),
        _mock_role_exposure_row(),
    ]
    stats = get_computed_stats("p1")
    assert stats["is_provisional"] is expected_tier
