from datetime import date, datetime
from pydantic import BaseModel, field_validator
from schemas.enums import MatchFormat


class SessionCreate(BaseModel):
    session_date: date
    session_minutes: int
    num_tables: int
    match_format: MatchFormat | None = None  # if omitted, inherits from event.default_match_format

    @field_validator("session_minutes")
    @classmethod
    def validate_minutes(cls, v: int) -> int:
        if v < 30:
            raise ValueError("session_minutes must be at least 30")
        return v

    @field_validator("num_tables")
    @classmethod
    def validate_tables(cls, v: int) -> int:
        if v < 1:
            raise ValueError("num_tables must be at least 1")
        return v


class SessionResponse(BaseModel):
    session_id: str
    event_id: str
    session_date: date
    session_minutes: int
    num_tables: int
    match_format: str
    bootstrap_phase: str
    rating_spread: float
    matches_per_player: int
    present_player_count: int
    status: str
    generated_at: datetime | None
    created_at: datetime


class GenerateFixturesRequest(BaseModel):
    player_ids: list[str]

    @field_validator("player_ids")
    @classmethod
    def at_least_two(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("At least 2 players required to generate fixtures")
        return v


class FixtureSlotResponse(BaseModel):
    slot_id: str
    round_number: int
    sub_round: str | None
    table_number: int
    match_category: str
    player_a: dict
    player_b: dict | None  # None when player_b is a BYE
    expected_rating_gap: float
    status: str
    match_id: str | None
    match_result: dict | None = None  # populated when status == PLAYED


class SessionFixturesResponse(BaseModel):
    session_id: str
    bootstrap_phase: str
    matches_per_player: int
    fixture_slots_created: int
    slots: list[FixtureSlotResponse]


class SessionStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"IN_PROGRESS", "COMPLETED", "CANCELLED"}
        if v not in valid:
            raise ValueError(f"status must be one of {valid}")
        return v
