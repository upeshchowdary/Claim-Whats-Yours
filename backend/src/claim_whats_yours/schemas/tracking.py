"""Pydantic request models for the tracking endpoints."""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

TrackingStatus = Literal["planned", "in_progress", "submitted", "approved", "rejected", "withdrawn"]


class TrackingCreate(BaseModel):
    """Body for creating a tracker record."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str | None = Field(default=None, max_length=64)
    status: TrackingStatus = "planned"
    progress_date: date | None = None
    reminder_date: date | None = None


class TrackingUpdate(BaseModel):
    """Body for partially updating a tracker record. At least one field must be set."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str | None = Field(default=None, max_length=64)
    status: TrackingStatus | None = None
    progress_date: date | None = None
    reminder_date: date | None = None

    @model_validator(mode="after")
    def _require_a_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        return self
