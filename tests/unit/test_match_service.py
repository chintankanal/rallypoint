"""Unit tests for match eligibility, canonical ordering, and deadline logic."""
from datetime import date, timezone

import pytest

from app.services.match_service import _canonical_order, _check_eligibility
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
