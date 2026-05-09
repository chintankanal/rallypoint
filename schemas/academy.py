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
