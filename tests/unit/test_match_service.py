"""Unit tests for match eligibility, canonical ordering, and deadline logic."""
from datetime import date, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.match_service import _canonical_order, _check_eligibility, store_set_scores, update_match
from app.utils.timezone import end_of_day_ist


# ---------- canonical ordering ----------

def test_canonical_order_already_sorted():
    a, b, sa, sb, saa, sba = _canonical_order(
        "aaa-player", "bbb-player", 2, 1, None, None
    )
    assert a == "aaa-player"
    assert b == "bbb-player"
    assert sa == 2 and sb == 1


def test_canonical_order_swaps_when_b_less():
    a, b, sa, sb, saa, sba = _canonical_order(
        "zzz-player", "aaa-player", 3, 1, 3, 1
    )
    assert a == "aaa-player"
    assert b == "zzz-player"
    assert sa == 1 and sb == 3      # scores swapped
    assert saa == 1 and sba == 3    # actual scores swapped too


# ---------- eligibility ----------

@pytest.mark.parametrize("ra,rb,sa,sb,is_ret,fmt,expected_eligible,expected_reason", [
    # Normal match — eligible
    (1000, 1000, 2, 1, False, "BO3", True,  None),
    # Walkover (0-0, not retirement)
    (1000, 1000, 0, 0, False, "BO3", False, "WALKOVER"),
    # Retirement with 0 sets
    (1000, 1000, 0, 0, True,  "BO3", False, "ZERO_SETS_RETIREMENT"),
    # Retirement with sets played — eligible
    (1000, 1000, 1, 0, True,  "BO3", True,  None),
    # Gap exactly 500 — eligible (boundary)
    (1500, 1000, 2, 0, False, "BO3", True,  None),
    # Gap 501 — not eligible
    (1501, 1000, 2, 0, False, "BO3", False, "RATING_GAP_EXCEEDED"),
    # Gap 501 reversed
    (1000, 1501, 2, 0, False, "BO3", False, "RATING_GAP_EXCEEDED"),
    # Gap 499 — eligible
    (1499, 1000, 2, 0, False, "BO3", True,  None),
])
def test_check_eligibility(ra, rb, sa, sb, is_ret, fmt, expected_eligible, expected_reason):
    eligible, reason = _check_eligibility(ra, rb, sa, sb, is_ret, fmt)
    assert eligible == expected_eligible
    assert reason == expected_reason


# ---------- confirmation deadline ----------

def test_deadline_is_stored_as_utc():
    d = date(2025, 1, 1)
    dt = end_of_day_ist(d)
    assert dt.tzinfo is not None
    # 23:59:59 IST = 18:29:59 UTC
    assert dt.astimezone(timezone.utc).hour == 18
    assert dt.astimezone(timezone.utc).minute == 29
    assert dt.astimezone(timezone.utc).second == 59


def test_deadline_date_boundary():
    # Make sure the date itself does not shift to next day in UTC
    d = date(2025, 6, 15)
    dt = end_of_day_ist(d)
    utc_dt = dt.astimezone(timezone.utc)
    assert utc_dt.date() == date(2025, 6, 15)


# ---------- set score schema validation ----------

def test_match_submit_invalid_best_of_3_scores():
    from schemas.match import MatchSubmit
    from schemas.enums import MatchFormat
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        MatchSubmit(
            event_id="e1",
            player_a_id="aaa",
            player_b_id="bbb",
            match_format=MatchFormat.BEST_OF_3,
            sets_won_a=1,   # winner needs exactly 2
            sets_won_b=0,
            is_retirement=False,
            match_date=date.today(),
        )


def test_match_submit_valid_best_of_3():
    from schemas.match import MatchSubmit
    from schemas.enums import MatchFormat

    m = MatchSubmit(
        event_id="e1",
        player_a_id="aaa",
        player_b_id="bbb",
        match_format=MatchFormat.BEST_OF_3,
        sets_won_a=2,
        sets_won_b=1,
        is_retirement=False,
        match_date=date.today(),
    )
    assert m.sets_won_a == 2


@pytest.mark.parametrize("sa,sb,fmt,valid", [
    (1, 0, "BEST_OF_1", True),
    (0, 0, "BEST_OF_1", False),   # winner needs 1
    (1, 1, "BEST_OF_1", False),   # invalid non-retirement score
    (2, 0, "BEST_OF_3", True),
    (2, 1, "BEST_OF_3", True),
    (1, 0, "BEST_OF_3", False),   # winner needs 2
    (3, 0, "BEST_OF_5", True),
    (3, 2, "BEST_OF_5", True),
    (2, 0, "BEST_OF_5", False),   # winner needs 3
    (4, 0, "BEST_OF_7", True),
    (4, 3, "BEST_OF_7", True),
    (3, 0, "BEST_OF_7", False),   # winner needs 4
])
def test_set_score_format_validation(sa, sb, fmt, valid):
    from schemas.match import MatchSubmit
    from schemas.enums import MatchFormat
    import pydantic

    kwargs = dict(
        event_id="e1",
        player_a_id="aaa",
        player_b_id="bbb",
        match_format=MatchFormat[fmt],
        sets_won_a=sa,
        sets_won_b=sb,
        is_retirement=False,
        match_date=date.today(),
    )
    if valid:
        m = MatchSubmit(**kwargs)
        assert m.sets_won_a == sa
    else:
        with pytest.raises(pydantic.ValidationError):
            MatchSubmit(**kwargs)


def test_confirm_request_requires_reason_when_disputing():
    from schemas.match import ConfirmMatchRequest
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ConfirmMatchRequest(confirmed=False, dispute_reason=None)


def test_confirm_request_valid_dispute():
    from schemas.match import ConfirmMatchRequest

    r = ConfirmMatchRequest(confirmed=False, dispute_reason="Score was wrong")
    assert r.dispute_reason == "Score was wrong"


def _make_mock_conn():
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.cursor.return_value.__exit__.return_value = False
    return mock_conn, mock_cur


def test_store_set_scores_replaces_existing_rows():
    mock_conn, mock_cur = _make_mock_conn()
    store_set_scores(mock_conn, "match-123", [
        {"points_a": 11, "points_b": 9},
        {"points_a": 11, "points_b": 7},
    ])

    assert mock_cur.execute.call_args_list[0] == (
        ("DELETE FROM match_set_score WHERE match_id = %s", ("match-123",)),
    )
    assert mock_cur.execute.call_args_list[1] == (
        ("INSERT INTO match_set_score (match_id, set_number, points_a, points_b) VALUES (%s, %s, %s, %s)", ("match-123", 1, 11, 9)),
    )
    assert mock_cur.execute.call_args_list[2] == (
        ("INSERT INTO match_set_score (match_id, set_number, points_a, points_b) VALUES (%s, %s, %s, %s)", ("match-123", 2, 11, 7)),
    )


def test_update_match_calls_store_set_scores_when_set_scores_present(monkeypatch):
    mock_conn, mock_cur = _make_mock_conn()

    saved = {}
    def fake_store_set_scores(conn, match_id, set_scores):
        saved["args"] = (conn, match_id, set_scores)

    monkeypatch.setattr("app.services.match_service.store_set_scores", fake_store_set_scores)
    monkeypatch.setattr("app.services.match_service._fetch_match", lambda cur, match_id, scheduling_mode: {"match_id": match_id})

    mock_cur.fetchone.side_effect = [
        {
            "match_id": "match-123",
            "event_id": "event-456",
            "session_id": None,
            "fixture_slot_id": None,
            "player_a_id": "player-a",
            "player_b_id": "player-b",
            "match_format": "BEST_OF_3",
            "is_retirement": False,
            "confirmation_status": "CONFIRMED",
            "ratings_applied_at": None,
            "sets_won_a": 2,
            "sets_won_b": 1,
            "sets_won_a_actual": 2,
            "sets_won_b_actual": 1,
        },
        {"player_id": "player-a", "current_rating": 1200},
        {"player_id": "player-b", "current_rating": 1180},
        {"scheduling_mode": "INTRA_ACADEMY"},
    ]
    mock_cur.fetchall.return_value = []

    body = SimpleNamespace(
        set_scores=[{"points_a": 11, "points_b": 9}, {"points_a": 11, "points_b": 7}],
        sets_won_a=2,
        sets_won_b=1,
        match_date=date(2025, 1, 1),
        is_retirement=None,
        sets_won_a_actual=None,
        sets_won_b_actual=None,
    )

    result = update_match(mock_conn, "match-123", body, "user-1")

    assert saved["args"][0] is mock_conn
    assert saved["args"][1] == "match-123"
    assert saved["args"][2] == body.set_scores
    assert result == {"match_id": "match-123"}


def test_update_match_does_not_call_store_set_scores_when_set_scores_is_none(monkeypatch):
    mock_conn, mock_cur = _make_mock_conn()

    called = False
    def fake_store_set_scores(conn, match_id, set_scores):
        nonlocal called
        called = True

    monkeypatch.setattr("app.services.match_service.store_set_scores", fake_store_set_scores)
    monkeypatch.setattr("app.services.match_service._fetch_match", lambda cur, match_id, scheduling_mode: {"match_id": match_id})

    mock_cur.fetchone.side_effect = [
        {
            "match_id": "match-123",
            "event_id": "event-456",
            "session_id": None,
            "fixture_slot_id": None,
            "player_a_id": "player-a",
            "player_b_id": "player-b",
            "match_format": "BEST_OF_3",
            "is_retirement": False,
            "confirmation_status": "CONFIRMED",
            "ratings_applied_at": None,
            "sets_won_a": 2,
            "sets_won_b": 1,
            "sets_won_a_actual": 2,
            "sets_won_b_actual": 1,
        },
        {"player_id": "player-a", "current_rating": 1200},
        {"player_id": "player-b", "current_rating": 1180},
        {"scheduling_mode": "INTRA_ACADEMY"},
    ]
    mock_cur.fetchall.return_value = []

    body = SimpleNamespace(
        set_scores=None,
        sets_won_a=2,
        sets_won_b=1,
        match_date=date(2025, 1, 1),
        is_retirement=None,
        sets_won_a_actual=None,
        sets_won_b_actual=None,
    )

    result = update_match(mock_conn, "match-123", body, "user-1")

    assert called is False
    assert result == {"match_id": "match-123"}
