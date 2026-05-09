from datetime import date, datetime
from pydantic import BaseModel


class RatingHistoryEntry(BaseModel):
    history_id: str
    match_id: str
    rating_before: float
    rating_after: float
    delta: float
    delta_breakdown: dict | None  # Visible only to player, coach, admin
    tier_before: str
    tier_after: str
    cr_before: float
    cr_after: float
    k_base: float
    k_eff: float
    k_shared: float
    expected_score: float
    actual_score: float
    age_bonus: float
    is_rollback: bool
    created_at: datetime
    match_date: date | None = None
    opponent_name: str | None = None
    result: str | None = None
    event_id: str | None = None
    event_name: str | None = None
    event_type: str | None = None
    session_id: str | None = None
    session_date: date | None = None
    match_category: str | None = None
    sets_won_a: int | None = None
    sets_won_b: int | None = None
    confirmation_status: str | None = None
    diminishing_signal_applied: bool | None = None
    opponent_rating_before: float | None = None


class PaginatedRatingHistory(BaseModel):
    player_id: str
    items: list[RatingHistoryEntry]
    total: int
    limit: int
    offset: int
