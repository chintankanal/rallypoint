from datetime import datetime, date
from pydantic import BaseModel, computed_field, field_validator, model_validator
from schemas.enums import EventType, SchedulingMode, MatchFormat, TournamentFormat, EventStatus

_VALID_COMBINATIONS = {
    ("INTRA_ACADEMY", "FRIENDLY"),
    ("INTER_ACADEMY", "LEAGUE"),
    ("INTER_ACADEMY", "TOURNAMENT_EXTERNAL"),
    ("INTER_ACADEMY", "TOURNAMENT_MANAGED"),
}


class EventCreate(BaseModel):
    season_id: str | None = None
    name: str
    scheduling_mode: SchedulingMode
    event_type: EventType
    default_match_format: MatchFormat | None = None
    tournament_format: TournamentFormat | None = None
    host_academy_id: str | None = None
    participating_academy_ids: list[str] = []
    start_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_combination_and_dates(self) -> "EventCreate":
        combo = (self.scheduling_mode.value, self.event_type.value)
        if combo not in _VALID_COMBINATIONS:
            raise ValueError(
                f"Invalid combination: {self.scheduling_mode} + {self.event_type}. "
                "INTRA_ACADEMY only supports FRIENDLY. "
                "INTER_ACADEMY supports LEAGUE, TOURNAMENT_EXTERNAL, TOURNAMENT_MANAGED."
            )
        if self.scheduling_mode == SchedulingMode.INTER_ACADEMY and self.end_date is None:
            raise ValueError("end_date is required for INTER_ACADEMY events")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class EventStatusUpdate(BaseModel):
    status: EventStatus


class AddAcademyToEvent(BaseModel):
    academy_id: str


class AssignRefereeRequest(BaseModel):
    user_id: str


class AssignUmpireRequest(BaseModel):
    user_id: str
    table_number: int

    @field_validator("table_number")
    @classmethod
    def table_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("table_number must be positive")
        return v


class EventResponse(BaseModel):
    event_id: str
    name: str
    scheduling_mode: str
    event_type: str
    default_match_format: str | None
    tournament_format: str | None = None
    season: dict | None
    participating_academies: list[dict]
    start_date: date
    end_date: date | None
    status: str
    created_at: datetime

    @computed_field
    @property
    def is_cross_academy(self) -> bool:
        return self.scheduling_mode == "INTER_ACADEMY"


class RefereeAssignmentResponse(BaseModel):
    assignment_id: str
    event_id: str
    user_id: str
    assigned_at: datetime


class UmpireAssignmentResponse(BaseModel):
    assignment_id: str
    event_id: str
    user_id: str
    table_number: int
    assigned_at: datetime


# ── Event player registration ─────────────────────────────────────────────────

class EventPlayerRegister(BaseModel):
    player_id: str


class EventPlayerItem(BaseModel):
    registration_id: str
    player_id: str
    name: str
    academy_id: str
    academy_name: str
    current_rating: float
    status: str
    registered_at: datetime


class EventRosterResponse(BaseModel):
    event_id: str
    total: int
    items: list[EventPlayerItem]


# ── Inter-academy fixture generation ─────────────────────────────────────────

_VALID_FIXTURE_STRATEGIES = {"FULL_ROUND_ROBIN", "TIER_MATCHED", "CROSS_ACADEMY_ONLY", "TEAM_FORMAT"}


class GenerateEventFixturesRequest(BaseModel):
    num_tables: int = 4
    fixture_strategy: str = "TIER_MATCHED"

    @field_validator("num_tables")
    @classmethod
    def validate_tables(cls, v: int) -> int:
        if v < 1:
            raise ValueError("num_tables must be at least 1")
        return v

    @field_validator("fixture_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        if v not in _VALID_FIXTURE_STRATEGIES:
            raise ValueError(f"fixture_strategy must be one of {sorted(_VALID_FIXTURE_STRATEGIES)}")
        return v


class EventFixturePlayer(BaseModel):
    player_id: str
    name: str
    current_rating: float
    academy_id: str
    academy_name: str


class EventFixtureSlotResponse(BaseModel):
    slot_id: str
    round_number: int
    table_number: int
    match_category: str
    player_a: EventFixturePlayer
    player_b: EventFixturePlayer | None
    expected_rating_gap: float
    status: str
    fixture_strategy: str
    match_id: str | None


class EventFixturesResponse(BaseModel):
    event_id: str
    total_rounds: int
    total_slots: int
    cross_academy_pct: float
    slots: list[EventFixtureSlotResponse]
