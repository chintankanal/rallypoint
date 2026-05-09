from datetime import datetime, date
from pydantic import BaseModel, field_validator, model_validator
from schemas.enums import SeasonStatus


class SeasonCreate(BaseModel):
    name: str
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def end_after_start(self) -> "SeasonCreate":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class SeasonResponse(BaseModel):
    season_id: str
    name: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime


class SeasonStatusUpdate(BaseModel):
    status: SeasonStatus
