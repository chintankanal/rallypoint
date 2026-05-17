from datetime import date, datetime
from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    player_id: str
    name: str
    current_rating: float
    tier: str
    academy_name: str | None
    is_provisional: bool
    rated_matches: int
    last_match_date: date | None
    gender: str | None = None
    age_group: str | None = None


class LeaderboardResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[LeaderboardEntry]


class AgeGroupLeaderboardEntry(BaseModel):
    rank: int
    player_id: str
    name: str
    current_rating: float
    tier: str
    academy_name: str | None
    age_jan1: int
    percentile: float
    gender: str | None = None
    age_group: str | None = None


class AgeGroupLeaderboardResponse(BaseModel):
    age_group: str
    total: int
    items: list[AgeGroupLeaderboardEntry]


class OverviewResponse(BaseModel):
    total_players: int
    matches_processed: int
    participating_academies: int


class VelocityReport(BaseModel):
    player_id: str
    period: str
    start_rating: float | None
    end_rating: float | None
    rating_change: float
    matches_played: int
    wins: int
    win_rate: float
    stretch_matches: int
    stretch_wins: int
    stretch_win_rate: float | None
    tier_changes: int


class TierCount(BaseModel):
    tier: str
    count: int


class TopMover(BaseModel):
    player_id: str
    name: str
    total_delta: float
    matches: int


class ASIPoint(BaseModel):
    asi_value: float | None
    calculation_basis: str
    calculated_at: datetime


class AcademyReport(BaseModel):
    academy_id: str
    period_days: int
    total_rated_matches: int
    cross_academy_count: int
    cross_academy_pct: float
    confirmed_count: int
    total_submitted: int
    confirmation_rate: float
    tier_distribution: list[TierCount]
    top_movers: list[TopMover]
    asi_trend: list[ASIPoint]


class ASIHistoryEntry(BaseModel):
    history_id: str
    asi_value: float | None
    qualifying_player_count: int
    calculation_basis: str
    global_average_at_calculation: float
    calculated_at: datetime


class ASIHistoryResponse(BaseModel):
    academy_id: str
    items: list[ASIHistoryEntry]


class ConfigEntry(BaseModel):
    key: str
    value: str
    description: str | None


class ConfigResponse(BaseModel):
    items: list[ConfigEntry]


class ConfigUpdate(BaseModel):
    value: str


class ConfigHistoryEntry(BaseModel):
    history_id: str
    key: str
    old_value: str
    new_value: str
    changed_at: datetime


class ConfigHistoryResponse(BaseModel):
    key: str | None
    total: int
    items: list[ConfigHistoryEntry]
