from datetime import datetime
from pydantic import BaseModel, field_validator


class AcademyCreate(BaseModel):
    name: str
    location: str
    city: str
    state: str
    min_tables: int

    @field_validator("min_tables")
    @classmethod
    def min_tables_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("min_tables must be at least 1")
        return v


class AcademyResponse(BaseModel):
    academy_id: str
    name: str
    location: str
    city: str
    state: str
    status: str
    min_tables: int
    created_at: datetime


class AcademyDetail(AcademyResponse):
    current_asi: float | None
    asi_player_count: int | None
    asi_last_calculated: datetime | None
    active_player_count: int


class TierDistribution(BaseModel):
    BEGINNER: int
    INTERMEDIATE: int
    ADVANCED: int
    ELITE: int
    NATIONAL_TRACK: int


class AcademyStats(BaseModel):
    academy_id: str
    tables_available: int
    active_player_count: int
    coach_count: int
    total_match_volume: int
    matches_30_days: int
    current_asi: float | None
    tier_distribution: TierDistribution
