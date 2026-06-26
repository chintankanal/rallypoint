from datetime import date, datetime
from pydantic import BaseModel, field_validator, model_validator
from schemas.enums import MatchFormat


class SetScore(BaseModel):
    sets_won_a: int
    sets_won_b: int

    @model_validator(mode="after")
    def validate_scores(self) -> "SetScore":
        if self.sets_won_a < 0 or self.sets_won_b < 0:
            raise ValueError("Set scores cannot be negative")
        return self


class SetPoints(BaseModel):
    points_a: int
    points_b: int

    @model_validator(mode="after")
    def validate_set_points(self) -> "SetPoints":
        if self.points_a < 0 or self.points_b < 0:
            raise ValueError("Set points cannot be negative")
        if self.points_a == 0 and self.points_b == 0:
            raise ValueError("A set must have points scored")
        if self.points_a > 30 or self.points_b > 30:
            raise ValueError("Set points cannot exceed 30")
        # Require winner to have at least 11 points
        if max(self.points_a, self.points_b) < 11:
            raise ValueError("Winning player in a set must have ≥11 points")
        return self


_REQUIRED_WINNER_SETS = {"BEST_OF_1": 1, "BEST_OF_3": 2, "BEST_OF_5": 3, "BEST_OF_7": 4}


class MatchSubmit(BaseModel):
    event_id: str
    session_id: str | None = None
    fixture_slot_id: str | None = None
    player_a_id: str
    player_b_id: str
    match_format: MatchFormat
    sets_won_a: int
    sets_won_b: int
    # For retirements: actual sets before the player retired (may differ from credited sets)
    sets_won_a_actual: int | None = None
    sets_won_b_actual: int | None = None
    is_retirement: bool = False
    match_date: date
    umpire_id: str | None = None
    # Optional per-set point scores for analytics; nullable for backward compatibility
    set_scores: list[SetPoints] | None = None

    @model_validator(mode="after")
    def validate_match(self) -> "MatchSubmit":
        if self.player_a_id == self.player_b_id:
            raise ValueError("player_a_id and player_b_id must be different players")

        fmt = self.match_format.value
        required = _REQUIRED_WINNER_SETS.get(fmt, 0)
        winner_sets = max(self.sets_won_a, self.sets_won_b)
        loser_sets = min(self.sets_won_a, self.sets_won_b)

        if not self.is_retirement:
            if winner_sets != required:
                raise ValueError(
                    f"{fmt} match winner must have exactly {required} sets; "
                    f"got {self.sets_won_a}-{self.sets_won_b}"
                )
        else:
            # Retirement: winner must have ≥ required sets OR match ended early
            # Validation is relaxed — service layer handles eligibility
            if winner_sets > required:
                raise ValueError(
                    f"Set score {self.sets_won_a}-{self.sets_won_b} exceeds max for {fmt}"
                )

        if loser_sets >= required:
            raise ValueError(
                f"Loser cannot have {loser_sets} sets in a {fmt} match"
            )

        return self


class ConfirmMatchRequest(BaseModel):
    confirmed: bool
    dispute_reason: str | None = None

    @model_validator(mode="after")
    def require_reason_on_dispute(self) -> "ConfirmMatchRequest":
        if not self.confirmed and not self.dispute_reason:
            raise ValueError("dispute_reason is required when confirmed=false")
        return self


class MatchUpdate(BaseModel):
    sets_won_a: int | None = None
    sets_won_b: int | None = None
    sets_won_a_actual: int | None = None
    sets_won_b_actual: int | None = None
    is_retirement: bool | None = None
    match_date: date | None = None
    set_scores: list[SetPoints] | None = None

    @model_validator(mode="after")
    def validate_update(self) -> "MatchUpdate":
        if (
            self.sets_won_a is None
            and self.sets_won_b is None
            and self.sets_won_a_actual is None
            and self.sets_won_b_actual is None
            and self.is_retirement is None
            and self.match_date is None
            and self.set_scores is None
        ):
            raise ValueError("At least one field must be provided for match updates")
        if (self.sets_won_a is None) != (self.sets_won_b is None):
            raise ValueError("Both sets_won_a and sets_won_b must be provided together")
        if self.set_scores is not None and (self.sets_won_a is None or self.sets_won_b is None):
            raise ValueError("sets_won_a and sets_won_b must accompany set_scores updates")
        if self.sets_won_a is not None and self.sets_won_a < 0:
            raise ValueError("sets_won_a cannot be negative")
        if self.sets_won_b is not None and self.sets_won_b < 0:
            raise ValueError("sets_won_b cannot be negative")
        return self


class MatchDeleteRequest(BaseModel):
    reason: str | None = None


class VoidMatchRequest(BaseModel):
    void_reason: str


class MatchResponse(BaseModel):
    match_id: str
    event_id: str
    session_id: str | None
    fixture_slot_id: str | None
    player_a: dict
    player_b: dict
    match_format: str
    sets_won_a: int
    sets_won_b: int
    sets_won_a_actual: int | None
    sets_won_b_actual: int | None
    is_retirement: bool
    winner_id: str
    rating_eligible: bool
    not_eligible_reason: str | None
    diminishing_signal_applied: bool
    confirmation_status: str
    confirmation_deadline: datetime
    ratings_applied_at: datetime | None
    ratings_trigger: str
    match_date: date
    match_timestamp: datetime
    created_at: datetime
    set_scores: list[dict] | None = None
