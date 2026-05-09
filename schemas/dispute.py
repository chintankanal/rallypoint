from datetime import datetime
from pydantic import BaseModel


class DisputeResponse(BaseModel):
    dispute_id: str
    match_id: str
    raised_by: str
    reason: str
    status: str
    resolution: str | None
    corrected_sets_won_a: int | None
    corrected_sets_won_b: int | None
    resolved_by: str | None
    resolution_notes: str | None
    resolution_deadline: datetime
    created_at: datetime
    resolved_at: datetime | None


class DisputeStatusUpdate(BaseModel):
    status: str

    def validate_status(self) -> None:
        if self.status != "UNDER_REVIEW":
            raise ValueError("Only UNDER_REVIEW is a valid status transition via this endpoint")


class DisputeResolveRequest(BaseModel):
    resolution: str
    corrected_sets_won_a: int | None = None
    corrected_sets_won_b: int | None = None
    resolution_notes: str | None = None

    def validate_resolution(self) -> None:
        valid = {"CONFIRMED_ORIGINAL", "CORRECTED", "VOIDED"}
        if self.resolution not in valid:
            raise ValueError(f"resolution must be one of {valid}")
        if self.resolution == "CORRECTED" and (
            self.corrected_sets_won_a is None or self.corrected_sets_won_b is None
        ):
            raise ValueError("corrected_sets_won_a and corrected_sets_won_b required for CORRECTED")


class PaginatedDisputeResponse(BaseModel):
    items: list[DisputeResponse]
    total: int
    limit: int
    offset: int
