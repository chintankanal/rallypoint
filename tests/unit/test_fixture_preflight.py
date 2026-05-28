"""
Unit tests for app/services/fixture_preflight.py (critique §14, §15, §16).
"""
from app.services.fixture_preflight import (
    W_DOMINANT_ACADEMY,
    W_SMALL_POOL,
    W_TEAM_FORMAT_IMBALANCE,
    preflight_event,
    preflight_session,
)


def _player(pid: str, rating: float, **extra) -> dict:
    return {"player_id": pid, "current_rating": rating, **extra}


# ── Intra-academy session preflight ──────────────────────────────────────────

def test_session_small_pool_emits_info():
    players = [_player(f"p{i}", 1000.0) for i in range(5)]
    warnings = preflight_session(players, num_tables=2, matches_per_player_estimate=3)
    codes = {w["code"] for w in warnings}
    assert W_SMALL_POOL in codes


def test_session_very_small_pool_emits_warn():
    players = [_player(f"p{i}", 1000.0) for i in range(3)]
    warnings = preflight_session(players, num_tables=2, matches_per_player_estimate=2)
    small = [w for w in warnings if w["code"] == W_SMALL_POOL]
    assert small and small[0]["severity"] == "WARN"


def test_session_zero_capacity_emits_error():
    players = [_player(f"p{i}", 1000.0) for i in range(8)]
    warnings = preflight_session(players, num_tables=1, matches_per_player_estimate=0)
    codes = {w["code"]: w["severity"] for w in warnings}
    assert codes.get("ZERO_CAPACITY") == "ERROR"


def test_session_healthy_pool_emits_no_warnings():
    players = [_player(f"p{i}", 1000.0 + i * 10) for i in range(20)]
    warnings = preflight_session(players, num_tables=10, matches_per_player_estimate=4)
    assert warnings == []


# ── Inter-academy event preflight ────────────────────────────────────────────

def _ia(pid: str, rating: float, academy: str) -> dict:
    return {
        "player_id": pid, "current_rating": rating,
        "academy_id": academy, "academy_name": academy.upper(),
    }


def test_event_dominant_academy_in_cross_academy_only_warns():
    """4-vs-1 skew should trigger DOMINANT_ACADEMY for CROSS_ACADEMY_ONLY."""
    players_by_academy = {
        "a": [_ia(f"a{i}", 1200.0, "a") for i in range(4)],
        "b": [_ia("b1", 1180.0, "b")],
    }
    warnings = preflight_event(
        players_by_academy, strategy="CROSS_ACADEMY_ONLY", num_tables=4,
    )
    codes = {w["code"] for w in warnings}
    assert W_DOMINANT_ACADEMY in codes


def test_event_dominant_academy_does_not_warn_for_tier_matched():
    """The dominant-academy warning is specific to CROSS_ACADEMY_ONLY."""
    players_by_academy = {
        "a": [_ia(f"a{i}", 1200.0, "a") for i in range(4)],
        "b": [_ia("b1", 1180.0, "b")],
    }
    warnings = preflight_event(
        players_by_academy, strategy="TIER_MATCHED", num_tables=4,
    )
    codes = {w["code"] for w in warnings}
    assert W_DOMINANT_ACADEMY not in codes


def test_event_team_format_imbalance_warns():
    """TEAM_FORMAT with 6-vs-2 rosters should warn about lineup imbalance."""
    players_by_academy = {
        "a": [_ia(f"a{i}", 1200.0, "a") for i in range(6)],
        "b": [_ia("b1", 1180.0, "b"), _ia("b2", 1170.0, "b")],
    }
    warnings = preflight_event(
        players_by_academy, strategy="TEAM_FORMAT", num_tables=4,
    )
    codes = {w["code"] for w in warnings}
    assert W_TEAM_FORMAT_IMBALANCE in codes


def test_event_balanced_team_format_no_imbalance_warning():
    """3-vs-3 rosters should NOT trigger the lineup imbalance warning."""
    players_by_academy = {
        "a": [_ia(f"a{i}", 1200.0, "a") for i in range(3)],
        "b": [_ia(f"b{i}", 1180.0, "b") for i in range(3)],
    }
    warnings = preflight_event(
        players_by_academy, strategy="TEAM_FORMAT", num_tables=4,
    )
    codes = {w["code"] for w in warnings}
    assert W_TEAM_FORMAT_IMBALANCE not in codes


def test_event_empty_roster_errors():
    warnings = preflight_event({}, strategy="TIER_MATCHED", num_tables=4)
    codes = {w["code"]: w["severity"] for w in warnings}
    assert codes.get("EMPTY_ROSTER") == "ERROR"


def test_event_warnings_all_have_required_fields():
    """Every emitted warning must carry code, severity, message, context."""
    players_by_academy = {
        "a": [_ia(f"a{i}", 1200.0, "a") for i in range(5)],
        "b": [_ia("b1", 1180.0, "b")],
    }
    warnings = preflight_event(
        players_by_academy, strategy="CROSS_ACADEMY_ONLY", num_tables=4,
    )
    for w in warnings:
        assert "code" in w and w["code"]
        assert w["severity"] in ("INFO", "WARN", "ERROR")
        assert "message" in w and w["message"]
        assert isinstance(w.get("context"), dict)
