from datetime import datetime, date
from pydantic import BaseModel, field_validator, model_validator
from schemas.enums import Gender, SeedingLevel
from schemas.event import EventFixtureSlotResponse


class PlayerCreate(BaseModel):
    name: str
    date_of_birth: date
    gender: Gender
    primary_academy_id: str
    seeding_level: SeedingLevel
    seeding_reference: str | None = None
    nationality: str = "India"
    guardian_name: str | None = None
    guardian_phone: str | None = None
    contact_email: str | None = None
    virtual_matches: int | None = None  # None = derive from seeding level

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, v: date) -> date:
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 6 or age > 18:
            raise ValueError("Player must be between 6 and 18 years old")
        return v

    @model_validator(mode="after")
    def check_seeding_reference(self) -> "PlayerCreate":
        if self.seeding_level != SeedingLevel.UNSEEDED and not self.seeding_reference:
            raise ValueError("seeding_reference is required for non-UNSEEDED players")
        return self


class PlayerResponse(BaseModel):
    player_id: str
    name: str
    date_of_birth: date
    gender: str | None
    nationality: str | None
    current_rating: float
    rated_matches_completed: int
    virtual_matches: int
    seeding_level: str
    primary_academy: dict
    last_match_date: date | None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    contact_email: str | None = None
    status: str
    is_claimed: bool
    claim_code: str | None = None
    created_at: datetime


class ClaimPlayerRequest(BaseModel):
    claim_code: str


class LinkAccountRequest(BaseModel):
    user_id: str


class PlayerComputedStats(BaseModel):
    player_id: str
    as_of: datetime
    age_as_of_jan1: int
    age_group: str
    total_matches: int
    is_provisional: bool
    provisional_matches_remaining: int
    tier: str
    confidence_ratio: float
    weeks_inactive: float | None
    inactivity_decay_active: bool


class AcademyTransferRequest(BaseModel):
    new_academy_id: str
    effective_date: date

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: date) -> date:
        if v.day != 1:
            raise ValueError("effective_date must be the 1st of a calendar month")
        if v <= date.today():
            raise ValueError("effective_date must be in the future")
        return v


class AcademyTransferResponse(BaseModel):
    player_id: str
    new_primary_academy_id: str
    effective_date: date
    next_change_allowed_after: date


class PlayerAcademyHistoryEntry(BaseModel):
    history_id: str
    academy: dict
    effective_from: date
    effective_to: date | None
    change_reason: str
    changed_by: str


class PlayerAcademyHistoryResponse(BaseModel):
    player_id: str
    history: list[PlayerAcademyHistoryEntry]


class PlayerEventFixtureItem(BaseModel):
    event_id: str
    name: str
    scheduling_mode: str
    event_type: str
    status: str
    fixture_state: str | None
    start_date: date
    end_date: date | None
    default_match_format: str | None
    slots: list[EventFixtureSlotResponse]


class PlayerEventFixturesResponse(BaseModel):
    player_id: str
    items: list[PlayerEventFixtureItem]
