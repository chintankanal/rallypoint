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
        if age < 6:
            raise ValueError("Player must be at least 6 years old")
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
    seeding_reference: str | None = None
    primary_academy: dict
    last_match_date: date | None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    contact_email: str | None = None
    status: str
    is_claimed: bool
    claim_code: str | None = None
    created_at: datetime


class PlayerUpdate(BaseModel):
    name: str | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None
    nationality: str | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = None
    contact_email: str | None = None
    seeding_level: SeedingLevel | None = None
    seeding_reference: str | None = None
    current_rating: float | None = None
    virtual_matches: int | None = None

    @model_validator(mode="after")
    def validate_update(self) -> "PlayerUpdate":
        if (
            self.name is None
            and self.date_of_birth is None
            and self.gender is None
            and self.nationality is None
            and self.guardian_name is None
            and self.guardian_phone is None
            and self.contact_email is None
            and self.seeding_level is None
            and self.seeding_reference is None
            and self.current_rating is None
            and self.virtual_matches is None
        ):
            raise ValueError("At least one field must be provided for player updates")
        if self.virtual_matches is not None and self.virtual_matches < 0:
            raise ValueError("Virtual matches cannot be negative")
        if self.current_rating is not None and self.current_rating < 0:
            raise ValueError("Current rating cannot be negative")
        if self.seeding_level is not None and self.seeding_level != SeedingLevel.UNSEEDED and not self.seeding_reference:
            raise ValueError("seeding_reference is required for seeded players")
        return self


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
    role_exposure: dict[str, int] = {}


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
